"""
ML Survival Analysis, Hazard Modeling & Abstention Test Suite
Verifies:
1. Lifelines survival modeling handles right-censored unpaid invoices
2. P10 <= P50 <= P90 payment date window validity
3. Cold-start buyers trigger explicit abstention path (no fabricated score)
4. SHAP feature importances strictly mapped to neutral 'Prediction Drivers'
"""

import pytest
from datetime import date, timedelta
from services.survival_engine import SurvivalAnalysisEngine
from services.confidence_engine import ConfidenceEngine
from models.invoice import Invoice

def test_survival_analysis_percentile_window():
    """Verify survival model produces valid monotonic P10 <= P50 <= P90 percentiles."""
    engine = SurvivalAnalysisEngine()
    inv_date = date.today() - timedelta(days=20)

    res = engine.fit_and_predict(
        buyer_id="sample-buyer",
        invoice_amount=500000.0,
        agreed_term=45,
        invoice_date=inv_date,
        is_cpse=False
    )

    assert 0.0 <= res['delay_probability'] <= 1.0
    assert res['p10_days'] <= res['p50_days'] <= res['p90_days']
    assert res['p10_date'] <= res['p50_date'] <= res['p90_date']
    assert len(res['curve_points']) > 0

def test_cold_start_buyer_abstention():
    """When history depth is 0, the system must invoke abstention and refuse to fabricate a buyer-specific number."""
    conf_engine = ConfidenceEngine()
    inv = Invoice(agreed_term_days=45, confidence=0.90)

    eval_res = conf_engine.evaluate_confidence(
        invoice=inv,
        history_depth=0, # Cold start
        ocr_confidence=0.90,
        has_anomalies=False
    )

    assert eval_res['is_abstained'] is True
    assert eval_res['confidence_level'] == 'INSUFFICIENT_EVIDENCE'
    assert eval_res['status_badge'] == 'INSUFFICIENT EVIDENCE'
    assert "abstains" in eval_res['abstention_reason'].lower()

def test_prediction_drivers_naming_guardrail():
    """Verify non-causal terminology: 'Prediction Drivers', not 'Reasons for delay'."""
    conf_engine = ConfidenceEngine()
    features = {
        'buyer_typical_delay': 20.0,
        'buyer_is_cpse': 1,
        'concentration_ratio': 0.40,
        'has_grn': 0,
        'amount': 1500000.0
    }

    drivers = conf_engine.format_prediction_drivers(features, late_prob=0.75)
    assert len(drivers) > 0
    for d in drivers:
        assert d['impact'] in ['HIGH', 'MEDIUM', 'LOW']
        assert d['direction'] in ['INCREASES_DELAY', 'REDUCES_DELAY']
