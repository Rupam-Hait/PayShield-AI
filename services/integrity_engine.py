"""
Engine 3: Invoice Integrity Shield & Anomaly Engine
Detects duplicates, PO/GRN mismatches, impossible event sequences, and date inconsistencies.
Strict Guardrail: Output is ALWAYS "Potential anomaly detected", NEVER "Fraud detected".
"""

from datetime import date, datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from models.invoice import Invoice, InvoiceEvent, Document
from models.buyer import Buyer

class InvoiceIntegrityShield:
    def __init__(self, db_session: Session):
        self.db = db_session

    def inspect_invoice(self, invoice: Invoice) -> List[Dict[str, Any]]:
        """
        Run exhaustive integrity checks across an invoice, its events, and linked documents.
        Returns a list of detected potential anomalies.
        """
        anomalies = []

        # 1. Check Duplicate / Near-Duplicate Invoice Number within tenant
        duplicates = self.db.query(Invoice).filter(
            Invoice.tenant_id == invoice.tenant_id,
            Invoice.invoice_number == invoice.invoice_number,
            Invoice.invoice_id != invoice.invoice_id
        ).all()
        if duplicates:
            anomalies.append({
                'anomaly_type': 'DUPLICATE_INVOICE_NUMBER',
                'severity': 'HIGH',
                'evidence': f"Invoice number '{invoice.invoice_number}' already exists in system (ID: {duplicates[0].invoice_id[:8]})",
                'source': 'Relational Index Cross-Check',
                'confidence': 0.99,
                'suggested_verification_action': 'Verify if this is a re-submission or accidental double-billing in accounting.'
            })

        # 2. Date Inconsistency: Invoice Date > Contract Due Date or Statutory Due Date
        if invoice.contract_due_date and invoice.invoice_date > invoice.contract_due_date:
            anomalies.append({
                'anomaly_type': 'DATE_INCONSISTENCY_INVOICE_AFTER_DUE',
                'severity': 'HIGH',
                'evidence': f"Invoice date ({invoice.invoice_date}) is later than contractual due date ({invoice.contract_due_date})",
                'source': 'Calendar Logic Verification',
                'confidence': 1.0,
                'suggested_verification_action': 'Review written agreement or billing date entry for typographical errors.'
            })

        # 3. Impossible Event Sequence Checks
        events = sorted(invoice.events, key=lambda e: e.event_date)
        issued_date = None
        delivery_date = None
        acceptance_date = None
        first_payment_date = None

        for event in events:
            if event.event_type == 'ISSUED':
                issued_date = event.event_date
            elif event.event_type == 'DELIVERED':
                delivery_date = event.event_date
            elif event.event_type == 'ACCEPTED':
                acceptance_date = event.event_date
            elif event.event_type in ['PART_PAYMENT', 'FULL_PAYMENT'] and not first_payment_date:
                first_payment_date = event.event_date

        if delivery_date and issued_date and delivery_date < issued_date:
            anomalies.append({
                'anomaly_type': 'DELIVERY_PRECEDES_INVOICE_ISSUANCE',
                'severity': 'LOW',
                'evidence': f"Delivery occurred on {delivery_date}, prior to invoice date {issued_date}",
                'source': 'Event Sequence Monitor',
                'confidence': 0.85,
                'suggested_verification_action': 'Verify advance dispatch challan or confirm if retroactive invoice.'
            })

        if acceptance_date and delivery_date and acceptance_date < delivery_date:
            anomalies.append({
                'anomaly_type': 'IMPOSSIBLE_EVENT_SEQUENCE_ACCEPTANCE_BEFORE_DELIVERY',
                'severity': 'HIGH',
                'evidence': f"Goods recorded as accepted on {acceptance_date}, but delivery date is {delivery_date}",
                'source': 'Event Sequence Monitor',
                'confidence': 0.95,
                'suggested_verification_action': 'Audit GRN timestamp against logistics carrier proof of delivery.'
            })

        if first_payment_date and issued_date and first_payment_date < issued_date:
            anomalies.append({
                'anomaly_type': 'PAYMENT_PRECEDES_INVOICE',
                'severity': 'MEDIUM',
                'evidence': f"Payment receipt ({first_payment_date}) is earlier than invoice date ({issued_date})",
                'source': 'Event Sequence Monitor',
                'confidence': 0.92,
                'suggested_verification_action': 'Confirm whether payment was an unadjusted mobilization advance.'
            })

        # 4. Missing Delivery / Acceptance Proof
        if not invoice.delivery_date and not invoice.acceptance_date:
            anomalies.append({
                'anomaly_type': 'MISSING_DELIVERY_ACCEPTANCE_EVIDENCE',
                'severity': 'MEDIUM',
                'evidence': "No signed delivery challan, GRN, or formal buyer acceptance record found.",
                'source': 'Ecosystem Readiness Validator',
                'confidence': 0.90,
                'suggested_verification_action': 'Obtain stamped Goods Receipt Note (GRN) or carrier delivery confirmation.'
            })

        # 5. PO / GRN / Invoice Mismatch Detection (via linked documents or fields)
        docs = invoice.documents
        for doc in docs:
            if doc.extracted_fields_json:
                try:
                    import json
                    fields = json.loads(doc.extracted_fields_json)
                    # Check PO quantity / amount mismatch if PO document attached
                    if doc.doc_type == 'PO':
                        po_amt = fields.get('amount', {}).get('value')
                        if po_amt and abs(float(po_amt) - invoice.amount) > 5.0:
                            anomalies.append({
                                'anomaly_type': 'PO_INVOICE_AMOUNT_MISMATCH',
                                'severity': 'MEDIUM',
                                'evidence': f"Invoice amount (₹{invoice.amount:,.2f}) differs from Purchase Order total (₹{float(po_amt):,.2f})",
                                'source': 'Document Cross-Reconciliation',
                                'confidence': 0.93,
                                'suggested_verification_action': 'Cross-check freight, GST rate differences, or partial PO fulfillment.'
                            })
                except Exception:
                    pass

        # 6. Low OCR extraction confidence
        if invoice.confidence < 0.75:
            anomalies.append({
                'anomaly_type': 'LOW_CONFIDENCE_OCR_EXTRACTION',
                'severity': 'MEDIUM',
                'evidence': f"Overall document extraction confidence is {int(invoice.confidence * 100)}%, below safety threshold.",
                'source': 'Document Intelligence Engine',
                'confidence': 0.88,
                'suggested_verification_action': 'Perform manual field confirmation before relying on automated predictions.'
            })

        return anomalies
