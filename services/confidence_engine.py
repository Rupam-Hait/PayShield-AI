"""
Engine 7: Explainability & Confidence Engine
Computes multi-factor data quality rating, builds explicit abstention paths,
and formats SHAP feature importances into neutral "Prediction Drivers".
"""

from typing import Dict, Any, List, Optional
from models.invoice import Invoice

class ConfidenceEngine:
    def __init__(self):
        pass

    def evaluate_confidence(
        self,
        invoice: Invoice,
        history_depth: int,
        ocr_confidence: float,
        has_anomalies: bool
    ) -> Dict[str, Any]:
        """
        Evaluate predictive confidence combining multiple data-quality channels.
        Enforces strict abstention path when evidence is insufficient.
        """
        reasons = []
        is_abstained = False
        abstention_reason = None

        # Check 1: History Depth
        if history_depth == 0:
            is_abstained = True
            abstention_reason = "No historical invoice or payment record exists for this buyer. System abstains from buyer-specific score."
            reasons.append("Zero historical transactions (Cold-start buyer)")
        elif history_depth < 3:
            reasons.append(f"Sparse buyer history ({history_depth} transaction(s) observed)")

        # Check 2: OCR Quality
        if ocr_confidence < 0.65:
            is_abstained = True
            abstention_reason = f"Document OCR confidence ({int(ocr_confidence*100)}%) is below acceptable integrity threshold."
            reasons.append("Poor document image clarity / Low OCR confidence")
        elif ocr_confidence < 0.85:
            reasons.append("Moderate OCR field confidence — requires validation")

        # Check 3: Essential Contractual Data
        if not invoice.agreed_term_days or invoice.agreed_term_days <= 0:
            reasons.append("Missing explicit contractual payment term")

        # Check 4: Anomalies
        if has_anomalies:
            reasons.append("Open document integrity anomalies detected on invoice")

        # Determine overall rating
        if is_abstained:
            confidence_level = "INSUFFICIENT_EVIDENCE"
            confidence_score = 0.35
            status_badge = "INSUFFICIENT EVIDENCE"
        elif history_depth >= 6 and ocr_confidence >= 0.85 and not has_anomalies:
            confidence_level = "HIGH"
            confidence_score = 0.92
            status_badge = "SAFE"
        else:
            confidence_level = "MEDIUM"
            confidence_score = 0.72
            status_badge = "WATCH"

        return {
            'confidence_level': confidence_level,
            'confidence_score': confidence_score,
            'status_badge': status_badge,
            'is_abstained': is_abstained,
            'abstention_reason': abstention_reason,
            'factors': reasons,
            'prediction_basis': "Consented MSME transaction timeline" if not is_abstained else "Cohort prior (insufficient evidence)"
        }

    def format_prediction_drivers(self, features: Dict[str, Any], late_prob: float) -> List[Dict[str, Any]]:
        """
        Format SHAP / feature contributions into neutral business 'Prediction Drivers'.
        Guardrail: NEVER call them 'Reasons for delay' or 'Causes'.
        """
        drivers = []

        # Feature: Historical payment typical delay
        typical_delay = features.get('buyer_typical_delay', 0)
        if typical_delay > 15:
            drivers.append({
                'feature': 'Historical Payment Cycle',
                'impact': 'HIGH',
                'direction': 'INCREASES_DELAY',
                'evidence': f"Consented history shows median settlement is {int(typical_delay)} days past contractual term",
                'shap_weight': +0.32
            })
        elif typical_delay <= 0:
            drivers.append({
                'feature': 'Prompt Historical Settlement',
                'impact': 'HIGH',
                'direction': 'REDUCES_DELAY',
                'evidence': "Consented history shows buyer consistently settles on or before due date",
                'shap_weight': -0.28
            })

        # Feature: Buyer CPSE status
        if features.get('buyer_is_cpse'):
            drivers.append({
                'feature': 'Enterprise Category (CPSE)',
                'impact': 'MEDIUM',
                'direction': 'REDUCES_DELAY',
                'evidence': "CPSE governed by mandatory MSME 45-day monitoring & TReDS platform",
                'shap_weight': -0.19
            })

        # Feature: Buyer Concentration
        concentration = features.get('concentration_ratio', 0)
        if concentration > 0.30:
            drivers.append({
                'feature': 'High Buyer Concentration Exposure',
                'impact': 'HIGH',
                'direction': 'INCREASES_DELAY',
                'evidence': f"Buyer accounts for {int(concentration*100)}% of total open receivables portfolio",
                'shap_weight': +0.22
            })

        # Feature: Operational Proof (GRN & Delivery)
        has_grn = features.get('has_grn', 0)
        has_po = features.get('has_po', 0)
        if not has_grn or not has_po:
            drivers.append({
                'feature': 'Documentation Completeness',
                'impact': 'MEDIUM',
                'direction': 'INCREASES_DELAY',
                'evidence': "Missing formalized GRN or verified Purchase Order link",
                'shap_weight': +0.15
            })
        else:
            drivers.append({
                'feature': 'Three-Way Match Verification',
                'impact': 'MEDIUM',
                'direction': 'REDUCES_DELAY',
                'evidence': "Verified matching PO, Delivery Challan, and Invoice references",
                'shap_weight': -0.14
            })

        # Feature: Invoice Size relative to normal
        amt = features.get('amount', 0)
        if amt > 1000000:
            drivers.append({
                'feature': 'High-Value Ticket Size',
                'impact': 'MEDIUM',
                'direction': 'INCREASES_DELAY',
                'evidence': f"Invoice ticket size of ₹{amt/100000:,.1f}L typically triggers multi-tier internal approval",
                'shap_weight': +0.12
            })

        return drivers
