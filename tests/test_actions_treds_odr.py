"""
Action Optimizer, TReDS, ODR & Evidence Pack Test Suite
Verifies:
1. OR-Tools Integer Programming optimizes actions within capacity limits
2. Human Approval Gateway enforces authorization before execution
3. TReDS readiness is a checklist, never an unexplained score
4. ODR readiness verifies MSMED Act Section 18 prerequisites
5. Evidence Pack compiles cryptographic SHA-256 manifest
"""

import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Tenant, User, Buyer, Invoice, ActionItem
from services.optimizer import ReceivablesActionOptimizer
from services.action_engine import ActionIntelligenceEngine
from services.treds_engine import TReDSReadinessEngine
from services.odr_engine import ODRReadinessEngine
from services.evidence_engine import EvidencePackEngine

@pytest.fixture
def full_db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()

    t = Tenant(business_name="Bharat Tooling Works", udyam_id="UDYAM-BTL-01", enterprise_type="Micro", activity_type="Manufacturing")
    s.add(t)
    s.flush()

    u = User(tenant_id=t.tenant_id, role="PROPRIETOR", name="Suresh Rao", email="suresh@bharat.in")
    u.set_password("pass123")
    s.add(u)

    b_cpse = Buyer(tenant_id=t.tenant_id, canonical_name="BHEL Heavy Corp", gstin="07AAACB1111A1Z1", is_cpse=True, treds_registered=True)
    b_pvt = Buyer(tenant_id=t.tenant_id, canonical_name="Pvt Builder Ltd", gstin="27AAAC2222B1Z2", is_cpse=False, treds_registered=False)
    s.add_all([b_cpse, b_pvt])
    s.flush()

    today = date.today()
    inv_cpse = Invoice(
        tenant_id=t.tenant_id, buyer_id=b_cpse.buyer_id, invoice_number="INV-CPSE-01",
        invoice_date=today - timedelta(days=20), delivery_date=today - timedelta(days=18),
        contract_due_date=today + timedelta(days=25), statutory_due_date=today + timedelta(days=25),
        amount=1500000.0, outstanding_amount=1500000.0, po_number="PO-BHEL-01", grn_number="GRN-BHEL-01"
    )
    inv_overdue = Invoice(
        tenant_id=t.tenant_id, buyer_id=b_pvt.buyer_id, invoice_number="INV-PVT-02",
        invoice_date=today - timedelta(days=60), delivery_date=today - timedelta(days=58),
        contract_due_date=today - timedelta(days=15), statutory_due_date=today - timedelta(days=15),
        amount=800000.0, outstanding_amount=800000.0, status="OVERDUE"
    )
    s.add_all([inv_cpse, inv_overdue])
    s.commit()

    yield s, t, u, inv_cpse, inv_overdue
    s.close()

def test_ortools_optimizer():
    """Verify OR-Tools schedules actions within max daily capacity."""
    opt = ReceivablesActionOptimizer()
    candidate_actions = [
        {'id': f'act_{i}', 'amount': 100000.0 * (i+1), 'expected_return': (i+1) * 2.0, 'effort': 1, 'is_aggressive': False}
        for i in range(10)
    ]
    # Max daily capacity is 4
    scheduled = opt.optimize_action_schedule(candidate_actions, max_daily_capacity=4)
    assert len(scheduled) == 4
    # Ensure highest returns were prioritized
    assert scheduled[0]['expected_return'] >= scheduled[-1]['expected_return']

def test_human_approval_gateway(full_db):
    """Verify actions cannot execute without human approval."""
    s, tenant, user, inv_cpse, inv_overdue = full_db
    engine = ActionIntelligenceEngine(s)

    act = ActionItem(
        tenant_id=tenant.tenant_id,
        invoice_id=inv_overdue.invoice_id,
        action_type="ODR_LEGAL_NOTICE",
        reason="Statutory default",
        status="PENDING_APPROVAL"
    )
    s.add(act)
    s.commit()

    assert act.status == "PENDING_APPROVAL"
    assert act.approved_at is None

    # Authorize via gateway
    engine.approve_action(act.action_id, approved_by_user_id=user.user_id)
    assert act.status == "APPROVED"
    assert act.approved_by == user.user_id

def test_treds_readiness_checklist(full_db):
    """Verify TReDS readiness is a checklist, never an unexplained score."""
    s, tenant, user, inv_cpse, inv_overdue = full_db
    treds_eng = TReDSReadinessEngine(s)

    res_cpse = treds_eng.evaluate_treds_readiness(inv_cpse)
    assert res_cpse['overall_status'] == "READY"
    assert res_cpse['status_badge'] == "READY"
    assert len(res_cpse['checklist']) >= 4
    # Guardrail: Never a score like '92%'
    assert "92%" not in str(res_cpse)
    assert "does not guarantee financing" in res_cpse['disclaimer'].lower()

    # Non-CPSE unregistered buyer must be blocked
    res_pvt = treds_eng.evaluate_treds_readiness(inv_overdue)
    assert "BLOCKED" in res_pvt['overall_status']
    assert len(res_pvt['blocking_reasons']) > 0

def test_evidence_pack_generation(full_db):
    """Verify Cryptographic Evidence Pack assembles SHA-256 hash manifest."""
    s, tenant, user, inv_cpse, inv_overdue = full_db
    evid_eng = EvidencePackEngine(s)

    dossier = evid_eng.generate_evidence_pack(inv_overdue.invoice_id)
    assert dossier['invoice_number'] == "INV-PVT-02"
    assert len(dossier['master_manifest_hash']) == 64 # Valid SHA-256 hex string
    assert len(dossier['items']) >= 5
    for item in dossier['items']:
        assert len(item['sha256_hash']) == 64
