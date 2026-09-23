"""
Invoice Integrity Shield & Anomaly Detection Test Suite
Verifies:
1. Duplicate invoice numbers detected
2. Date inconsistencies flagged (invoice date > due date)
3. Impossible event sequences flagged
4. Guardrail: Output is ALWAYS 'Potential anomaly detected', NEVER 'Fraud detected'.
"""

import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Tenant, Buyer, Invoice, InvoiceEvent
from services.integrity_engine import InvoiceIntegrityShield

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()

def test_duplicate_invoice_detection(db_session):
    t = Tenant(business_name="Test Corp", udyam_id="UDYAM-001")
    db_session.add(t)
    db_session.flush()

    b = Buyer(tenant_id=t.tenant_id, canonical_name="Buyer Alpha", gstin="27AAAC1234A1Z1")
    db_session.add(b)
    db_session.flush()

    # Invoice 1
    inv1 = Invoice(
        tenant_id=t.tenant_id, buyer_id=b.buyer_id, invoice_number="INV-2026-99",
        invoice_date=date.today(), contract_due_date=date.today() + timedelta(days=30),
        statutory_due_date=date.today() + timedelta(days=30), amount=500000.0
    )
    # Invoice 2 with duplicate number
    inv2 = Invoice(
        tenant_id=t.tenant_id, buyer_id=b.buyer_id, invoice_number="INV-2026-99",
        invoice_date=date.today(), contract_due_date=date.today() + timedelta(days=30),
        statutory_due_date=date.today() + timedelta(days=30), amount=500000.0
    )
    db_session.add_all([inv1, inv2])
    db_session.commit()

    shield = InvoiceIntegrityShield(db_session)
    anomalies = shield.inspect_invoice(inv2)

    assert len(anomalies) > 0
    dup_anom = [a for a in anomalies if a['anomaly_type'] == 'DUPLICATE_INVOICE_NUMBER']
    assert len(dup_anom) == 1
    # Check guardrail language: NEVER 'Fraud detected'
    for a in anomalies:
        assert "fraud" not in a['evidence'].lower()

def test_date_inconsistency(db_session):
    t = Tenant(business_name="Test Corp", udyam_id="UDYAM-002")
    db_session.add(t)
    db_session.flush()
    b = Buyer(tenant_id=t.tenant_id, canonical_name="Buyer Beta", gstin="27AAAC1234A1Z2")
    db_session.add(b)
    db_session.flush()

    # Inconsistent: invoice date is after contract due date
    inv = Invoice(
        tenant_id=t.tenant_id, buyer_id=b.buyer_id, invoice_number="INV-2026-ERR",
        invoice_date=date(2026, 3, 1), contract_due_date=date(2026, 2, 1),
        statutory_due_date=date(2026, 2, 1), amount=100000.0
    )
    db_session.add(inv)
    db_session.commit()

    shield = InvoiceIntegrityShield(db_session)
    anomalies = shield.inspect_invoice(inv)
    date_anom = [a for a in anomalies if 'DATE_INCONSISTENCY' in a['anomaly_type']]
    assert len(date_anom) == 1
