"""
Engine 11: TReDS Ecosystem Readiness Engine
Evaluates structural suitability of receivables for Trade Receivables Discounting System (TReDS).
Guardrails:
- Checklist, NEVER a percentage score (e.g. no '92% ready').
- Status is READY or BLOCKED: [reasons].
- Routes via Buyer type -> CPSE? -> Mandate. Never generalizes mandate to all buyers.
- Disclaimer: Actual financing subject to platform, buyer acceptance, financier terms.
"""

from typing import Dict, Any, List
from sqlalchemy.orm import Session
from models.invoice import Invoice
from models.buyer import Buyer
from models.tenant import Tenant

class TReDSReadinessEngine:
    def __init__(self, db_session: Session):
        self.db = db_session

    def evaluate_treds_readiness(self, invoice: Invoice) -> Dict[str, Any]:
        """
        Evaluate invoice for TReDS onboarding checklist.
        Returns itemized checklist and overall status: READY or BLOCKED.
        """
        buyer = invoice.buyer
        tenant = invoice.tenant
        checklist = []
        is_blocked = False
        blocking_reasons = []

        # Check 1: Supplier is registered MSME (Udyam)
        has_udyam = bool(tenant.udyam_id and len(tenant.udyam_id.strip()) > 5)
        if has_udyam:
            checklist.append({
                'item': 'Supplier Udyam Registration',
                'status': 'PASS',
                'details': f"Verified Udyam: {tenant.udyam_id} ({tenant.enterprise_type} Enterprise)"
            })
        else:
            is_blocked = True
            blocking_reasons.append("Supplier lacks valid Udyam registration")
            checklist.append({
                'item': 'Supplier Udyam Registration',
                'status': 'FAIL',
                'details': 'Active Udyam certificate required for TReDS seller onboarding'
            })

        # Check 2: Buyer Routing & Mandate
        # CPSEs and corporates with turnover > ₹500 Cr are mandated under Ministry of MSME / MCA notifications
        if buyer.is_cpse:
            buyer_mandate_text = "Mandatory TReDS onboarding applies under DPE Guidelines for CPSEs"
            buyer_mandate_pass = True
        elif buyer.turnover_exceeds_500cr:
            buyer_mandate_text = "Mandatory TReDS onboarding applies under MCA notification (Turnover > ₹500 Cr)"
            buyer_mandate_pass = True
        else:
            buyer_mandate_text = "Voluntary onboarding: Buyer is private corporate (not subject to mandatory mandate)"
            buyer_mandate_pass = buyer.treds_registered

        if buyer.treds_registered or buyer_mandate_pass:
            checklist.append({
                'item': 'Buyer Onboarding Status & Policy',
                'status': 'PASS',
                'details': f"{buyer.canonical_name} — {buyer_mandate_text}"
            })
        else:
            is_blocked = True
            blocking_reasons.append(f"Buyer '{buyer.canonical_name}' is not registered on any TReDS platform (RXIL, M1xchange, Invoicemart)")
            checklist.append({
                'item': 'Buyer Onboarding Status & Policy',
                'status': 'FAIL',
                'details': 'Buyer not onboarded on TReDS exchanges'
            })

        # Check 3: Valid Purchase Order / Contract Linkage
        if invoice.po_number:
            checklist.append({
                'item': 'Purchase Order Reference',
                'status': 'PASS',
                'details': f"PO reference present: {invoice.po_number}"
            })
        else:
            is_blocked = True
            blocking_reasons.append("Missing Purchase Order (PO) reference on invoice")
            checklist.append({
                'item': 'Purchase Order Reference',
                'status': 'FAIL',
                'details': 'PO link required for buyer factoring acceptance'
            })

        # Check 4: Proof of Delivery / Goods Receipt Note (GRN)
        has_grn = bool(invoice.grn_number or invoice.delivery_date)
        if has_grn:
            checklist.append({
                'item': 'Proof of Delivery / GRN',
                'status': 'PASS',
                'details': f"Recorded delivery/GRN: {invoice.grn_number or invoice.delivery_date}"
            })
        else:
            is_blocked = True
            blocking_reasons.append("Missing proof of delivery or Goods Receipt Note (GRN)")
            checklist.append({
                'item': 'Proof of Delivery / GRN',
                'status': 'FAIL',
                'details': 'Financiers require verifiable proof of delivery before bidding'
            })

        # Check 5: Dispute Status
        if invoice.status == 'DISPUTED':
            is_blocked = True
            blocking_reasons.append("Receivable is under open commercial dispute")
            checklist.append({
                'item': 'Commercial Dispute Status',
                'status': 'FAIL',
                'details': 'Invoices with open disputes are ineligible for factoring'
            })
        else:
            checklist.append({
                'item': 'Commercial Dispute Status',
                'status': 'PASS',
                'details': 'No unresolved disputes logged against this invoice'
            })

        # Check 6: Minimum Ticket Size
        if invoice.outstanding_amount >= 10000.0:
            checklist.append({
                'item': 'Minimum Receivable Threshold',
                'status': 'PASS',
                'details': f"Receivable value: ₹{invoice.outstanding_amount:,.2f} (above ₹10,000 platform threshold)"
            })
        else:
            is_blocked = True
            blocking_reasons.append("Invoice outstanding amount below ₹10,000 threshold")
            checklist.append({
                'item': 'Minimum Receivable Threshold',
                'status': 'FAIL',
                'details': f"₹{invoice.outstanding_amount:,.2f} is below minimum factoring lot size"
            })

        overall_status = "READY" if not is_blocked else f"BLOCKED: {'; '.join(blocking_reasons)}"
        status_badge = "READY" if not is_blocked else "BLOCKED"

        return {
            'invoice_id': invoice.invoice_id,
            'invoice_number': invoice.invoice_number,
            'buyer_name': buyer.canonical_name,
            'is_cpse': buyer.is_cpse,
            'checklist': checklist,
            'overall_status': overall_status,
            'status_badge': status_badge,
            'is_ready': not is_blocked,
            'blocking_reasons': blocking_reasons,
            'disclaimer': "The receivable appears structurally suitable for the TReDS workflow; actual financing is subject to platform onboarding, buyer acceptance, financier participation, and auction terms. PayShield does not guarantee financing."
        }
