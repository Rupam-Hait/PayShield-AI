"""
Legal Payment Clock & MSMED Act Regulatory Engine Test Suite
Verifies:
1. Section 15: Contractual term capped at statutory 45 days
2. Section 15 Proviso: Where no written agreement exists, capped at 15 days
3. Section 2(b): Deemed acceptance after 15 days from delivery
4. Section 16: Compound interest accrued at 3x RBI Bank Rate with monthly rests
"""

import pytest
from datetime import date, timedelta
from services.legal_rules import LegalPaymentClockEngine
from models.tenant import Tenant

def test_statutory_45_day_cap():
    """If agreement specifies 90 days, statute strictly caps due date at 45 days."""
    engine = LegalPaymentClockEngine()
    inv_date = date(2026, 1, 1)
    
    # Written agreement for 90 days
    clock = LegalPaymentClockEngine().calculate_legal_payment_clock(
        invoice_date=inv_date,
        delivery_date=inv_date,
        acceptance_date=inv_date,
        written_agreement=True,
        agreed_term_days=90,
        as_of_date=date(2026, 3, 1)
    )

    # Contractual date would be +90 days, but statutory due date must be capped at 45 days
    assert clock['is_contract_capped_by_statute'] is True
    assert clock['statutory_due_date'] == inv_date + timedelta(days=45)
    assert clock['contractual_due_date'] == inv_date + timedelta(days=90)

def test_no_written_agreement_15_day_limit():
    """Where no written agreement exists, payment is due on or before 15 days."""
    engine = LegalPaymentClockEngine()
    inv_date = date(2026, 1, 1)
    
    clock = engine.calculate_legal_payment_clock(
        invoice_date=inv_date,
        delivery_date=inv_date,
        acceptance_date=inv_date,
        written_agreement=False,
        agreed_term_days=0,
        as_of_date=date(2026, 1, 20)
    )

    assert clock['statutory_due_date'] == inv_date + timedelta(days=15)
    assert clock['days_overdue_statutory'] == 4 # 20 Jan - 16 Jan = 4 days overdue

def test_deemed_acceptance_15_days():
    """If goods delivered but no explicit acceptance note, deemed acceptance occurs on day 15."""
    engine = LegalPaymentClockEngine()
    deliv_date = date(2026, 2, 1)
    
    clock = engine.calculate_legal_payment_clock(
        invoice_date=deliv_date,
        delivery_date=deliv_date,
        acceptance_date=None,
        written_agreement=True,
        agreed_term_days=30,
        as_of_date=date(2026, 2, 20)
    )

    assert clock['acceptance_type'] == "DEEMED_ACCEPTANCE"
    assert clock['deemed_acceptance_date'] == deliv_date + timedelta(days=15)

def test_section_16_compound_interest():
    """Accrue compound interest at 3x RBI rate (20.25% p.a.) compounded monthly."""
    engine = LegalPaymentClockEngine()
    due_date = date(2026, 1, 1)
    as_of = date(2026, 4, 1) # 90 days of default (approx 3 months)
    principal = 1000000.0 # ₹10 Lakhs

    res = engine.calculate_statutory_interest(
        principal_amount=principal,
        statutory_due_date=due_date,
        as_of_date=as_of,
        annual_rate=20.25 # 3 * 6.75%
    )

    assert res['days_default'] == 90
    assert res['interest_accrued'] > 50000.0 # ~5.1% quarterly compound interest
    assert res['total_claimable'] == principal + res['interest_accrued']
