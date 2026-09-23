"""
Engine 11: ODR & MSEFC Statutory Readiness Engine
Evaluates structural prerequisites for statutory arbitration under Section 18 of the MSMED Act 2006.
Guardrails:
- Checklist, NEVER a percentage score.
- Output is READY or BLOCKED: [reasons].
- Application never presents itself as a law firm or legal authority.
- No guaranteed legal outcome or recovery.
"""

from datetime import date
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from models.invoice import Invoice
from models.buyer import Buyer
from models.tenant import Tenant
from services.legal_rules import LegalPaymentClockEngine

class ODRReadinessEngine:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.legal_clock = LegalPaymentClockEngine(db_session)

    def evaluate_odr_readiness(self, invoice: Invoice, as_of_date: date = None) -> Dict[str, Any]:
        """
        Evaluate statutory prerequisites for filing a reference before the Micro and Small
        Enterprises Facilitation Council (MSEFC) or statutory Online Dispute Resolution (ODR).
        """
        if as_of_date is None:
            as_of_date = date.today()

        tenant = invoice.tenant
        buyer = invoice.buyer
        checklist = []
        is_blocked = False
        blocking_reasons = []

        # 1. Enterprise Category Eligibility
        ent_eval = self.legal_clock.evaluate_enterprise_eligibility(tenant)
        if ent_eval['is_eligible']:
            checklist.append({
                'item': 'MSMED Act Enterprise Standing',
                'status': 'PASS',
                'details': f"Verified {tenant.enterprise_type} Enterprise in {tenant.activity_type} under Udyam {tenant.udyam_id}"
            })
        else:
            is_blocked = True
            reason_str = "; ".join(ent_eval['reasons'])
            blocking_reasons.append(reason_str)
            checklist.append({
                'item': 'MSMED Act Enterprise Standing',
                'status': 'FAIL',
                'details': reason_str
            })

        # 2. Statutory Due Date Breach Check
        clock = self.legal_clock.calculate_legal_payment_clock(
            invoice_date=invoice.invoice_date,
            delivery_date=invoice.delivery_date,
            acceptance_date=invoice.acceptance_date,
            written_agreement=invoice.written_agreement_exists,
            agreed_term_days=invoice.agreed_term_days,
            as_of_date=as_of_date
        )

        if clock['days_overdue_statutory'] > 0:
            checklist.append({
                'item': 'Statutory Default Maturity (Sec 15)',
                'status': 'PASS',
                'details': f"Payment is {clock['days_overdue_statutory']} days past statutory due date ({clock['statutory_due_date']})"
            })
        else:
            is_blocked = True
            blocking_reasons.append(f"Statutory due date ({clock['statutory_due_date']}) has not expired yet ({clock['days_until_statutory_breach']} days remaining)")
            checklist.append({
                'item': 'Statutory Default Maturity (Sec 15)',
                'status': 'FAIL',
                'details': f"Invoice is still within statutory payment window until {clock['statutory_due_date']}"
            })

        # 3. Delivery / Deemed Acceptance Proof
        if invoice.delivery_date or invoice.acceptance_date or invoice.grn_number:
            checklist.append({
                'item': 'Proof of Delivery / Acceptance (Sec 2b)',
                'status': 'PASS',
                'details': f"Documented basis: {clock['acceptance_type']} on {clock['base_clock_date']}"
            })
        else:
            is_blocked = True
            blocking_reasons.append("Missing proof of delivery or written acceptance notice")
            checklist.append({
                'item': 'Proof of Delivery / Acceptance (Sec 2b)',
                'status': 'FAIL',
                'details': 'Carrier consignment note or stamped delivery challan required by MSEFC'
            })

        # 4. Purchase Order / Contractual Documentation
        if invoice.po_number or invoice.written_agreement_exists:
            checklist.append({
                'item': 'Commercial Agreement / Purchase Order',
                'status': 'PASS',
                'details': f"Contractual agreement reference: {invoice.po_number or 'Written Sales Agreement'}"
            })
        else:
            checklist.append({
                'item': 'Commercial Agreement / Purchase Order',
                'status': 'PASS',
                'details': 'Oral/Implied contract: 15-day statutory deemed window applies under Section 15 Proviso'
            })

        # 5. Calculation of Compound Statutory Interest (Sec 16)
        interest_info = self.legal_clock.calculate_statutory_interest(
            principal_amount=invoice.outstanding_amount,
            statutory_due_date=clock['statutory_due_date'],
            as_of_date=as_of_date
        )

        checklist.append({
            'item': 'Statutory Interest Computation (Sec 16)',
            'status': 'PASS',
            'details': f"Accrued compound interest: ₹{interest_info['interest_accrued']:,.2f} at {interest_info['annual_rate']}% p.a. (3x RBI Bank Rate)"
        })

        overall_status = "READY" if not is_blocked else f"BLOCKED: {'; '.join(blocking_reasons)}"
        status_badge = "READY" if not is_blocked else "BLOCKED"

        return {
            'invoice_id': invoice.invoice_id,
            'invoice_number': invoice.invoice_number,
            'buyer_name': buyer.canonical_name,
            'statutory_due_date': clock['statutory_due_date'],
            'days_overdue': clock['days_overdue_statutory'],
            'interest_info': interest_info,
            'checklist': checklist,
            'overall_status': overall_status,
            'status_badge': status_badge,
            'is_ready': not is_blocked,
            'blocking_reasons': blocking_reasons,
            'disclaimer': "PayShield is an intelligence platform and does not provide legal representation or legal advice. MSEFC application eligibility is indicative; outcomes are governed strictly by the competent Facilitation Council."
        }
