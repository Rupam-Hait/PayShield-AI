"""
Engine 6: Payment-Time Prediction & Survival Inference Orchestrator
Coordinates Point-in-Time feature generation, survival analysis,
integrity checks, confidence evaluation, and driver formatting.
"""

from datetime import date, datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from models.invoice import Invoice
from models.prediction import Prediction, Explanation
from models.base import generate_uuid, utc_now
from ml.features import PointInTimeFeatureStore
from services.survival_engine import SurvivalAnalysisEngine
from services.confidence_engine import ConfidenceEngine
from services.integrity_engine import InvoiceIntegrityShield

class PredictionOrchestrator:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.feature_store = PointInTimeFeatureStore(db_session)
        self.survival_engine = SurvivalAnalysisEngine(db_session)
        self.confidence_engine = ConfidenceEngine()
        self.integrity_shield = InvoiceIntegrityShield(db_session)

    def predict_invoice(self, invoice_id: str, as_of_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Execute full end-to-end predictive pipeline for a single invoice.
        Enforces Point-in-Time integrity and explicit abstention when data is sparse.
        """
        invoice = self.db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        if as_of_date is None:
            as_of_date = date.today()

        # Step 1: Point-in-Time Features
        features = self.feature_store.extract_features(invoice_id, as_of_date)

        # Step 2: Anomaly / Integrity Checks
        anomalies = self.integrity_shield.inspect_invoice(invoice)
        has_anomalies = len(anomalies) > 0

        # Step 3: Confidence & Abstention Evaluation
        conf_eval = self.confidence_engine.evaluate_confidence(
            invoice=invoice,
            history_depth=features['history_depth'],
            ocr_confidence=features['ocr_confidence'],
            has_anomalies=has_anomalies
        )

        # Step 4: Survival / Hazard Modeling
        survival_res = self.survival_engine.fit_and_predict(
            buyer_id=invoice.buyer_id,
            invoice_amount=invoice.amount,
            agreed_term=invoice.agreed_term_days,
            invoice_date=invoice.invoice_date,
            as_of_date=as_of_date,
            is_cpse=invoice.buyer.is_cpse
        )

        # If abstained, adjust probabilities to reflect uncertainty
        delay_prob = survival_res['delay_probability']
        if conf_eval['is_abstained']:
            prediction_basis = "Cohort Prior Baseline (Cold Start / Insufficient Data)"
        else:
            prediction_basis = "Consented historical MSME transaction data"

        # Step 5: Format SHAP / Prediction Drivers
        drivers = self.confidence_engine.format_prediction_drivers(features, delay_prob)

        # Step 6: Persist Prediction & Explanations to Database
        prediction = Prediction(
            prediction_id=generate_uuid(),
            invoice_id=invoice.invoice_id,
            tenant_id=invoice.tenant_id,
            as_of_timestamp=utc_now(),
            delay_probability=delay_prob,
            p10_payment_date=survival_res['p10_date'],
            p50_payment_date=survival_res['p50_date'],
            p90_payment_date=survival_res['p90_date'],
            expected_delay_days=survival_res['expected_delay_days'],
            confidence=conf_eval['confidence_level'],
            confidence_score=conf_eval['confidence_score'],
            is_abstained=conf_eval['is_abstained'],
            abstention_reason=conf_eval['abstention_reason'],
            prediction_basis=prediction_basis,
            model_version="v1.0.0-survival-cox"
        )
        self.db.add(prediction)

        for d in drivers:
            expl = Explanation(
                explanation_id=generate_uuid(),
                prediction_id=prediction.prediction_id,
                feature=d['feature'],
                impact=d['impact'],
                direction=d['direction'],
                shap_value=d['shap_weight'],
                evidence_event=d['evidence']
            )
            self.db.add(expl)

        self.db.commit()

        return {
            'prediction_id': prediction.prediction_id,
            'delay_probability': delay_prob,
            'p10_date': survival_res['p10_date'],
            'p50_date': survival_res['p50_date'],
            'p90_date': survival_res['p90_date'],
            'expected_delay_days': survival_res['expected_delay_days'],
            'confidence': conf_eval['confidence_level'],
            'confidence_score': conf_eval['confidence_score'],
            'is_abstained': conf_eval['is_abstained'],
            'abstention_reason': conf_eval['abstention_reason'],
            'prediction_basis': prediction_basis,
            'anomalies': anomalies,
            'drivers': drivers,
            'payment_probabilities': survival_res['payment_probabilities'],
            'curve_points': survival_res['curve_points']
        }
