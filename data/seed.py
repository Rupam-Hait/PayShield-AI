"""
Demo & Seed Data Populator for PayShield AI
Initializes 1 MSME tenant, 5 distinct buyer regimes (CPSE, deteriorating, mismatch, cold-start, partial payer),
invoices, event timelines, documents, payments, scheduled cash obligations, and versioned legal rules.
Supports on-demand 'LOAD DEMO SCENARIO' reset.
"""

from datetime import date, datetime, timedelta, timezone
from sqlalchemy.orm import Session
from models.base import utc_now, generate_uuid
from models.tenant import Tenant, User, ConsentLedger, AuditLog
from models.buyer import Buyer
from models.invoice import Invoice, InvoiceEvent, Document
from models.payment import Payment
from models.cashflow import CashFlow
from models.rules import RuleVersion
from services.legal_rules import DEFAULT_RULES

def seed_database(db: Session, force_reset: bool = False):
    """Populate database with comprehensive seed scenario."""
    existing_tenant = db.query(Tenant).filter_by(udyam_id="UDYAM-MH-01-0029411").first()
    if existing_tenant and not force_reset:
        return existing_tenant

    if force_reset:
        # Clear tables
        for model in [AuditLog, ConsentLedger, Payment, InvoiceEvent, Document, Invoice, Buyer, User, CashFlow, Tenant, RuleVersion]:
            db.query(model).delete()
        db.commit()

    # 1. Seed Versioned Legal Rules
    for r_key, r_val in DEFAULT_RULES.items():
        rule = RuleVersion(
            rule_id=generate_uuid(),
            jurisdiction="INDIA_FEDERAL",
            rule_name=r_key,
            version=r_val['version'],
            effective_from=date(2006, 10, 2),
            effective_to=None,
            source=r_val['source'],
            numeric_value=r_val['value'],
            description=r_val['description']
        )
        db.add(rule)

    # 2. Seed MSME Tenant
    tenant = Tenant(
        tenant_id="tenant-apex-001",
        business_name="Apex Precision Tools Pvt Ltd",
        udyam_id="UDYAM-MH-01-0029411",
        industry="Automotive & Precision Engineering",
        state="Maharashtra",
        district="Pune",
        enterprise_type="Micro",
        activity_type="Manufacturing",
        annual_turnover=38000000.0, # ₹3.8 Crore
        created_at=utc_now()
    )
    db.add(tenant)

    # 3. Seed Users
    admin_user = User(
        user_id="user-proprietor-001",
        tenant_id=tenant.tenant_id,
        role="PROPRIETOR",
        name="Vikram Joshi",
        email="admin@apexprecision.in",
        phone="+91 98200 44551",
        auth_status="ACTIVE"
    )
    admin_user.set_password("admin123")
    db.add(admin_user)

    cfo_user = User(
        user_id="user-cfo-002",
        tenant_id=tenant.tenant_id,
        role="CFO",
        name="Neha Shenoy",
        email="neha@apexprecision.in",
        phone="+91 98200 44552",
        auth_status="ACTIVE"
    )
    cfo_user.set_password("cfo123")
    db.add(cfo_user)

    # 4. Seed DPDP Consent Ledgers
    for purpose in ['RECEIVABLES_ANALYSIS', 'CASHFLOW_TWIN', 'TREDS_SHARING', 'ACCOUNT_AGGREGATOR', 'PEER_BENCHMARKING']:
        consent = ConsentLedger(
            consent_id=generate_uuid(),
            tenant_id=tenant.tenant_id,
            user_id=admin_user.user_id,
            purpose=purpose,
            status='GRANTED',
            granted_at=utc_now(),
            dpdp_notice_version="2025.1",
            ip_address="127.0.0.1"
        )
        db.add(consent)

    # 5. Seed Buyers across 5 regimes
    today = date.today()

    # Buyer 1: CPSE (Safe, TReDS Mandated)
    buyer_bhel = Buyer(
        buyer_id="buyer-bhel-001",
        tenant_id=tenant.tenant_id,
        canonical_name="Bharat Heavy Electricals Ltd (BHEL)",
        gstin="07AAACB2212M1Z0",
        buyer_type="CPSE",
        is_cpse=True,
        turnover_exceeds_500cr=True,
        treds_registered=True,
        industry="Heavy Engineering & Energy",
        location="New Delhi",
        standard_payment_terms_days=45
    )
    db.add(buyer_bhel)

    # Buyer 2: Deteriorating Buyer (High Concentration Risk)
    buyer_delta = Buyer(
        buyer_id="buyer-delta-002",
        tenant_id=tenant.tenant_id,
        canonical_name="Delta Infrastructure Corp Ltd",
        gstin="27AAACD9911K1Z4",
        buyer_type="PRIVATE_CORP",
        is_cpse=False,
        turnover_exceeds_500cr=False,
        treds_registered=False,
        industry="Civil Infrastructure",
        location="Mumbai, Maharashtra",
        standard_payment_terms_days=45
    )
    db.add(buyer_delta)

    # Buyer 3: Operational Mismatch Buyer (PO/GRN Issue)
    buyer_sterling = Buyer(
        buyer_id="buyer-sterling-003",
        tenant_id=tenant.tenant_id,
        canonical_name="Sterling Automotives Ltd",
        gstin="24AAACS7733L1ZB",
        buyer_type="PRIVATE_CORP",
        is_cpse=False,
        turnover_exceeds_500cr=True,
        treds_registered=True,
        industry="Automotive Components",
        location="Vadodara, Gujarat",
        standard_payment_terms_days=30
    )
    db.add(buyer_sterling)

    # Buyer 4: Cold-Start New Buyer (Zero Historical Invoices -> Triggers Abstention)
    buyer_zenith = Buyer(
        buyer_id="buyer-zenith-004",
        tenant_id=tenant.tenant_id,
        canonical_name="Zenith Solar Technologies Pvt Ltd",
        gstin="29AAACZ1144N1ZR",
        buyer_type="PRIVATE_CORP",
        is_cpse=False,
        turnover_exceeds_500cr=False,
        treds_registered=False,
        industry="Renewable Energy",
        location="Bengaluru, Karnataka",
        standard_payment_terms_days=45
    )
    db.add(buyer_zenith)

    # Buyer 5: Partial Payer
    buyer_kavita = Buyer(
        buyer_id="buyer-kavita-005",
        tenant_id=tenant.tenant_id,
        canonical_name="Kavita Heavy Machinery Works",
        gstin="27AAACK5522P1Z7",
        buyer_type="PRIVATE_CORP",
        is_cpse=False,
        turnover_exceeds_500cr=False,
        treds_registered=False,
        industry="Industrial Fabrication",
        location="Nashik, Maharashtra",
        standard_payment_terms_days=45
    )
    db.add(buyer_kavita)

    db.flush()

    # 6. Seed Historical Invoices for BHEL (Prompt Payer history)
    for idx, days_ago in enumerate([180, 130, 90, 50]):
        inv_d = today - timedelta(days=days_ago)
        due_d = inv_d + timedelta(days=45)
        inv = Invoice(
            invoice_id=f"inv-hist-bhel-{idx}",
            tenant_id=tenant.tenant_id,
            buyer_id=buyer_bhel.buyer_id,
            invoice_number=f"INV-BHEL-2025-{100+idx}",
            invoice_date=inv_d,
            delivery_date=inv_d + timedelta(days=2),
            acceptance_date=inv_d + timedelta(days=5),
            written_agreement_exists=True,
            agreed_term_days=45,
            contract_due_date=due_d,
            statutory_due_date=due_d,
            amount=850000.0,
            status="PAID",
            paid_amount=850000.0,
            outstanding_amount=0.0,
            confidence=0.96,
            po_number=f"PO-BHEL-{4000+idx}",
            grn_number=f"GRN-BHEL-{8000+idx}"
        )
        db.add(inv)
        db.flush()
        # Payment event
        pay = Payment(
            payment_id=generate_uuid(),
            invoice_id=inv.invoice_id,
            tenant_id=tenant.tenant_id,
            payment_date=due_d - timedelta(days=2),
            amount=850000.0,
            reference=f"RTGS-BHEL-00{idx}"
        )
        db.add(pay)

    # 7. Seed Historical Invoices for Delta (Deteriorating Trend)
    # Earlier paid in 38 days, then 55 days, then 68 days
    delta_delays = [38, 52, 65]
    for idx, pay_days in enumerate(delta_delays):
        inv_d = today - timedelta(days=160 - idx * 45)
        due_d = inv_d + timedelta(days=45)
        inv = Invoice(
            invoice_id=f"inv-hist-delta-{idx}",
            tenant_id=tenant.tenant_id,
            buyer_id=buyer_delta.buyer_id,
            invoice_number=f"INV-DLT-2025-{200+idx}",
            invoice_date=inv_d,
            delivery_date=inv_d + timedelta(days=3),
            acceptance_date=inv_d + timedelta(days=7),
            written_agreement_exists=True,
            agreed_term_days=45,
            contract_due_date=due_d,
            statutory_due_date=due_d,
            amount=1400000.0,
            status="PAID",
            paid_amount=1400000.0,
            outstanding_amount=0.0,
            confidence=0.92,
            po_number=f"PO-DLT-{5000+idx}",
            grn_number=f"GRN-DLT-{9000+idx}"
        )
        db.add(inv)
        db.flush()
        pay = Payment(
            payment_id=generate_uuid(),
            invoice_id=inv.invoice_id,
            tenant_id=tenant.tenant_id,
            payment_date=inv_d + timedelta(days=pay_days),
            amount=1400000.0,
            reference=f"NEFT-DLT-00{idx}"
        )
        db.add(pay)

    # 8. Seed ACTIVE Open Invoices for the Demo Narrative
    # Invoice 1: BHEL - High Value, Safe, TReDS Ready
    inv_bhel_open = Invoice(
        invoice_id="inv-bhel-open-01",
        tenant_id=tenant.tenant_id,
        buyer_id=buyer_bhel.buyer_id,
        invoice_number="INV-2026-BHEL-09",
        invoice_date=today - timedelta(days=20),
        delivery_date=today - timedelta(days=18),
        acceptance_date=today - timedelta(days=15),
        written_agreement_exists=True,
        agreed_term_days=45,
        contract_due_date=today + timedelta(days=25),
        statutory_due_date=today + timedelta(days=25),
        amount=1850000.0, # ₹18.5 Lakhs
        status="ACCEPTED",
        paid_amount=0.0,
        outstanding_amount=1850000.0,
        confidence=0.97,
        po_number="PO-BHEL-2026-991",
        grn_number="GRN-BHEL-2026-442"
    )
    db.add(inv_bhel_open)

    # Invoice 2: Delta Corp - High Concentration Risk, Already Overdue (48 days old)
    inv_delta_open = Invoice(
        invoice_id="inv-delta-open-02",
        tenant_id=tenant.tenant_id,
        buyer_id=buyer_delta.buyer_id,
        invoice_number="INV-2026-DLT-88",
        invoice_date=today - timedelta(days=48),
        delivery_date=today - timedelta(days=45),
        acceptance_date=today - timedelta(days=40),
        written_agreement_exists=True,
        agreed_term_days=45,
        contract_due_date=today - timedelta(days=3),
        statutory_due_date=today - timedelta(days=3),
        amount=4200000.0, # ₹42 Lakhs (Large concentration)
        status="OVERDUE",
        paid_amount=0.0,
        outstanding_amount=4200000.0,
        statutory_interest_accrued=14200.0,
        confidence=0.94,
        po_number="PO-DLT-2026-104",
        grn_number="GRN-DLT-2026-880"
    )
    db.add(inv_delta_open)

    # Invoice 3: Sterling Automotives - Document Mismatch (PO amount differs from Invoice)
    inv_sterling_open = Invoice(
        invoice_id="inv-sterling-open-03",
        tenant_id=tenant.tenant_id,
        buyer_id=buyer_sterling.buyer_id,
        invoice_number="INV-2026-STR-41",
        invoice_date=today - timedelta(days=25),
        delivery_date=today - timedelta(days=22),
        acceptance_date=None, # Missing explicit acceptance!
        written_agreement_exists=True,
        agreed_term_days=30,
        contract_due_date=today + timedelta(days=5),
        statutory_due_date=today + timedelta(days=5),
        amount=650000.0, # PO states ₹580,000
        status="DELIVERED",
        paid_amount=0.0,
        outstanding_amount=650000.0,
        confidence=0.74, # Lower OCR confidence
        po_number="PO-STR-2026-550",
        grn_number=None
    )
    db.add(inv_sterling_open)

    # Invoice 4: Zenith Solar - Cold-Start Buyer (0 prior history -> Triggers Abstention)
    inv_zenith_open = Invoice(
        invoice_id="inv-zenith-open-04",
        tenant_id=tenant.tenant_id,
        buyer_id=buyer_zenith.buyer_id,
        invoice_number="INV-2026-ZNT-01",
        invoice_date=today - timedelta(days=10),
        delivery_date=today - timedelta(days=8),
        acceptance_date=today - timedelta(days=5),
        written_agreement_exists=True,
        agreed_term_days=45,
        contract_due_date=today + timedelta(days=35),
        statutory_due_date=today + timedelta(days=35),
        amount=950000.0,
        status="ACCEPTED",
        paid_amount=0.0,
        outstanding_amount=950000.0,
        confidence=0.88,
        po_number="PO-ZNT-2026-001",
        grn_number="GRN-ZNT-2026-012"
    )
    db.add(inv_zenith_open)

    # Invoice 5: Kavita Machinery - Partial Payments Stream
    inv_kavita_open = Invoice(
        invoice_id="inv-kavita-open-05",
        tenant_id=tenant.tenant_id,
        buyer_id=buyer_kavita.buyer_id,
        invoice_number="INV-2026-KAV-12",
        invoice_date=today - timedelta(days=35),
        delivery_date=today - timedelta(days=33),
        acceptance_date=today - timedelta(days=30),
        written_agreement_exists=True,
        agreed_term_days=45,
        contract_due_date=today + timedelta(days=10),
        statutory_due_date=today + timedelta(days=10),
        amount=1200000.0,
        status="PARTIALLY_PAID",
        paid_amount=400000.0, # 1st partial receipt
        outstanding_amount=800000.0,
        confidence=0.91,
        po_number="PO-KAV-2026-300",
        grn_number="GRN-KAV-2026-702"
    )
    db.add(inv_kavita_open)
    db.flush()

    # Add partial payment record for Kavita
    kavita_pay = Payment(
        payment_id=generate_uuid(),
        invoice_id=inv_kavita_open.invoice_id,
        tenant_id=tenant.tenant_id,
        payment_date=today - timedelta(days=10),
        amount=400000.0,
        reference="NEFT-KAV-PARTIAL-1"
    )
    db.add(kavita_pay)

    # 9. Seed Canonical Timeline Events for open invoices
    # For Delta Open
    db.add(InvoiceEvent(
        event_id=generate_uuid(),
        invoice_id=inv_delta_open.invoice_id,
        tenant_id=tenant.tenant_id,
        event_type="ISSUED",
        event_date=inv_delta_open.invoice_date,
        source="ACCOUNTING_ERP",
        confidence=1.0,
        notes="Tax Invoice generated from Tally ERP"
    ))
    db.add(InvoiceEvent(
        event_id=generate_uuid(),
        invoice_id=inv_delta_open.invoice_id,
        tenant_id=tenant.tenant_id,
        event_type="DELIVERED",
        event_date=inv_delta_open.delivery_date,
        source="LOGISTICS_POD",
        confidence=0.95,
        notes="Consignment delivered at Mumbai site"
    ))
    db.add(InvoiceEvent(
        event_id=generate_uuid(),
        invoice_id=inv_delta_open.invoice_id,
        tenant_id=tenant.tenant_id,
        event_type="ACCEPTED",
        event_date=inv_delta_open.acceptance_date,
        source="BUYER_PORTAL",
        confidence=0.92,
        notes="GRN-DLT-2026-880 signed by store manager"
    ))
    db.add(InvoiceEvent(
        event_id=generate_uuid(),
        invoice_id=inv_delta_open.invoice_id,
        tenant_id=tenant.tenant_id,
        event_type="DUE",
        event_date=inv_delta_open.statutory_due_date,
        source="LEGAL_CLOCK",
        confidence=1.0,
        notes="Statutory Section 15 payment deadline breached"
    ))

    # 10. Seed Scheduled Cashflow Obligations (Deterministic expenses)
    cash_events = [
        ('OUTFLOW', 'PAYROLL', 450000.0, today + timedelta(days=(30 - today.day) % 30 + 1), "Monthly Factory Payroll & Wages"),
        ('OUTFLOW', 'TAX', 220000.0, today + timedelta(days=(20 - today.day) % 30), "GST Return GSTR-3B Tax Dues"),
        ('OUTFLOW', 'EMI', 110000.0, today + timedelta(days=(10 - today.day) % 30), "Machinery Term Loan EMI"),
        ('OUTFLOW', 'VENDOR', 350000.0, today + timedelta(days=12), "Raw Material Steel Supplier Payment"),
        ('OUTFLOW', 'RENT', 85000.0, today + timedelta(days=5), "MIDC Industrial Shed Lease")
    ]
    for c_type, c_cat, c_amt, c_date, c_desc in cash_events:
        cf = CashFlow(
            cashflow_id=generate_uuid(),
            tenant_id=tenant.tenant_id,
            date=c_date,
            type=c_type,
            category=c_cat,
            amount=c_amt,
            description=c_desc,
            certainty="DETERMINISTIC",
            source="FINANCIAL_CALENDAR"
        )
        db.add(cf)

    # 11. Seed Audit Log for Demo Initialization
    audit = AuditLog(
        audit_id=generate_uuid(),
        tenant_id=tenant.tenant_id,
        user_id=admin_user.user_id,
        action="DEMO_SCENARIO_LOADED",
        object_type="System",
        object_id="ALL",
        timestamp=utc_now(),
        before_state="Empty Database",
        after_state="5 Buyers, 9 Invoices, CashFlows, Rules, and Events Initialized"
    )
    db.add(audit)

    db.commit()
    return tenant
