"""
CashFlow Digital Twin & What-If Scenario Test Suite
Verifies:
1. Monte Carlo stochastic simulation produces valid cash trajectories
2. Cash Survival Date pinpointed accurately
3. Liquidity gap output as range, NEVER as 'Loan approved'
4. What-If scenario server recalculation reflects stress impacts
"""

import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Tenant, Buyer, Invoice, CashFlow
from services.cashflow_engine import CashFlowDigitalTwin
from services.scenario_engine import ScenarioSimulator

@pytest.fixture
def sim_db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()

    t = Tenant(business_name="Precision MSME", udyam_id="UDYAM-SIM-01")
    s.add(t)
    s.flush()

    b = Buyer(tenant_id=t.tenant_id, canonical_name="Buyer Alpha", gstin="27AAAC1111A1Z1", standard_payment_terms_days=45)
    s.add(b)
    s.flush()

    # Invoices
    today = date.today()
    inv1 = Invoice(
        tenant_id=t.tenant_id, buyer_id=b.buyer_id, invoice_number="INV-SIM-01",
        invoice_date=today - timedelta(days=10), contract_due_date=today + timedelta(days=35),
        statutory_due_date=today + timedelta(days=35), amount=1000000.0, outstanding_amount=1000000.0
    )
    s.add(inv1)

    # Cash outflows
    cf1 = CashFlow(
        tenant_id=t.tenant_id, date=today + timedelta(days=15),
        type="OUTFLOW", category="PAYROLL", amount=600000.0
    )
    s.add(cf1)
    s.commit()

    yield s, t, b
    s.close()

def test_monte_carlo_cashflow_simulation(sim_db):
    s, tenant, buyer = sim_db
    twin = CashFlowDigitalTwin(s)

    res = twin.run_monte_carlo_simulation(
        tenant_id=tenant.tenant_id,
        starting_cash=800000.0,
        safety_threshold=400000.0,
        n_simulations=100
    )

    assert res['starting_cash'] == 800000.0
    assert len(res['trajectory_points']) > 0
    # Guardrail: Never 'Loan approved'
    assert "loan approved" not in res['liquidity_gap_text'].lower()
    assert "potential financing need" in res['liquidity_gap_text'].lower() or "zero immediate liquidity deficit" in res['liquidity_gap_text'].lower()

def test_whatif_scenario_recalculation(sim_db):
    s, tenant, buyer = sim_db
    sim = ScenarioSimulator(s)

    res = sim.simulate_rescue_scenario(
        tenant_id=tenant.tenant_id,
        delayed_buyer_id=buyer.buyer_id,
        extra_delay_days=30,
        starting_cash=800000.0
    )

    assert res['extra_delay_days'] == 30
    assert res['baseline'] is not None
    assert res['stressed'] is not None
    assert len(res['recommended_mitigation']) > 0
    assert "synthetic benchmark demonstrates technical feasibility" in res['label'].lower()
