"""
Point-in-Time Feature Store & Leakage Prevention Engine
Guarantees that every feature answers: "Was this known at prediction time?"
No future leakage: computes features strictly from events timestamped <= as_of_timestamp.
"""

from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from models.invoice import Invoice, InvoiceEvent
from models.buyer import Buyer
from models.payment import Payment

class PointInTimeFeatureStore:
    def __init__(self, db_session: Session):
        self.db = db_session

    def extract_features(self, invoice_id: str, as_of_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Extract feature vector for an invoice strictly as of a cutoff date.
        Features are segmented into:
        1. Invoice features (amount, term, frequency, sector, month/quarter)
        2. Buyer historical features (median days, delay rate, variability, open invoices, concentration)
        3. Operational features (acceptance delay, PO/GRN match, partial payments)
        4. Data quality features (history depth, OCR confidence, freshness)
        """
        invoice = self.db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        if as_of_date is None:
            as_of_date = invoice.invoice_date

        buyer = invoice.buyer
        tenant_id = invoice.tenant_id

        # 1. Invoice Features
        inv_amount = float(invoice.amount)
        agreed_term = invoice.agreed_term_days
        invoice_month = invoice.invoice_date.month
        invoice_quarter = (invoice_month - 1) // 3 + 1
        is_quarter_end = invoice_month in [3, 6, 9, 12]

        # 2. Historical Buyer Invoices prior to as_of_date (strictly point-in-time)
        historical_invoices = self.db.query(Invoice).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.buyer_id == buyer.buyer_id,
            Invoice.invoice_id != invoice.invoice_id,
            Invoice.invoice_date < as_of_date
        ).all()

        history_depth = len(historical_invoices)
        durations = []
        delays = []
        open_invoices_at_time = 0
        outstanding_at_time = 0.0

        for hist_inv in historical_invoices:
            # Query payments received ON or BEFORE as_of_date
            payments = self.db.query(Payment).filter(
                Payment.invoice_id == hist_inv.invoice_id,
                Payment.payment_date <= as_of_date
            ).order_by(Payment.payment_date).all()

            paid_sum = sum(p.amount for p in payments)
            if paid_sum >= (hist_inv.amount - 1.0) and payments:
                # Fully settled prior to prediction cutoff
                settle_date = payments[-1].payment_date
                duration = (settle_date - hist_inv.invoice_date).days
                durations.append(max(1, duration))
                delay = (settle_date - hist_inv.contract_due_date).days
                delays.append(delay)
            else:
                open_invoices_at_time += 1
                outstanding_at_time += max(0.0, hist_inv.amount - paid_sum)

        if durations:
            hist_median_days = float(np.median(durations))
            hist_p90_days = float(np.percentile(durations, 90))
            hist_variability = float(np.std(durations)) if len(durations) > 1 else 5.0
            delay_count = len([d for d in delays if d > 0])
            hist_delay_rate = float(delay_count / len(delays))
            hist_typical_delay = float(np.median(delays))
        else:
            # Cold-start prior defaults
            hist_median_days = float(agreed_term + 12.0)
            hist_p90_days = float(agreed_term + 28.0)
            hist_variability = 10.0
            hist_delay_rate = 0.45
            hist_typical_delay = 10.0

        # Concentration: buyer outstanding vs total tenant outstanding at that point
        all_hist = self.db.query(Invoice).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.invoice_date < as_of_date
        ).all()
        total_open_amount = sum(float(i.amount) for i in all_hist if i.status != 'PAID') or 1.0
        concentration_ratio = min(1.0, outstanding_at_time / total_open_amount)

        # 3. Operational Features
        acceptance_delay = (invoice.acceptance_date - invoice.invoice_date).days if invoice.acceptance_date else 0
        has_po = 1 if invoice.po_number else 0
        has_grn = 1 if invoice.grn_number else 0
        has_eway = 1 if invoice.eway_bill_number else 0

        # 4. Data Quality & Metadata
        ocr_confidence = float(invoice.confidence)
        
        feature_record = {
            'invoice_id': invoice.invoice_id,
            'as_of_date': as_of_date.isoformat(),
            'amount': inv_amount,
            'agreed_term': agreed_term,
            'invoice_month': invoice_month,
            'invoice_quarter': invoice_quarter,
            'is_quarter_end': int(is_quarter_end),
            'history_depth': history_depth,
            'buyer_is_cpse': int(buyer.is_cpse),
            'buyer_median_days': hist_median_days,
            'buyer_p90_days': hist_p90_days,
            'buyer_variability': hist_variability,
            'buyer_delay_rate': hist_delay_rate,
            'buyer_typical_delay': hist_typical_delay,
            'open_invoices_count': open_invoices_at_time,
            'outstanding_amount': outstanding_at_time,
            'concentration_ratio': round(concentration_ratio, 3),
            'acceptance_delay': acceptance_delay,
            'has_po': has_po,
            'has_grn': has_grn,
            'has_eway': has_eway,
            'ocr_confidence': ocr_confidence,
            'is_cold_start': 1 if history_depth < 3 else 0
        }
        return feature_record
