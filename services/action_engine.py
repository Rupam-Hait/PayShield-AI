"""
Engine 10: Action Intelligence & Human Approval Gateway
Generates relationship-preserving recovery actions, runs OR-Tools optimization,
enforces mandatory human approval, and records learning loop feedback.
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from models.action import ActionItem
from models.invoice import Invoice
from models.tenant import User
from models.base import generate_uuid, utc_now
from services.optimizer import ReceivablesActionOptimizer
from services.identity_service import IdentityService

class ActionIntelligenceEngine:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.optimizer = ReceivablesActionOptimizer()
        self.identity_service = IdentityService(db_session)

    def generate_recommended_actions(self, tenant_id: str, escalation_profile: str = "BALANCED") -> List[Dict[str, Any]]:
        """
        Evaluate all open invoices for tenant and generate deterministic, explainable actions.
        Applies escalation rules (Conservative, Balanced, Aggressive).
        """
        today = date.today()
        open_invoices = self.db.query(Invoice).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.status.in_(['ISSUED', 'DELIVERED', 'ACCEPTED', 'PARTIALLY_PAID'])
        ).all()

        candidate_actions = []

        for inv in open_invoices:
            due_date = inv.contract_due_date
            days_overdue = (today - due_date).days if due_date else 0
            is_overdue = days_overdue > 0
            amount = float(inv.outstanding_amount)
            buyer = inv.buyer

            # Check existing action
            existing = self.db.query(ActionItem).filter(
                ActionItem.invoice_id == inv.invoice_id,
                ActionItem.status.in_(['PENDING_APPROVAL', 'APPROVED'])
            ).first()

            # Rule 1: Missing acceptance or GRN
            if not inv.acceptance_date and not inv.grn_number:
                action_type = 'VERIFY_ACCEPTANCE'
                stage = 'Stage 1 — Verification'
                reason = "No confirmed delivery challan or acceptance note recorded. Clarify receipt before due date."
                channel = 'PORTAL'
                is_aggressive = False
                effort = 1
                return_weight = (amount / 100000.0) * 1.2
            # Rule 2: Overdue > 30 days — Escalation
            elif days_overdue > 30:
                if escalation_profile == "AGGRESSIVE" or days_overdue > 45:
                    action_type = 'ODR_LEGAL_NOTICE'
                    stage = 'Stage 5 — Statutory Notice'
                    reason = f"Statutory limit exceeded ({days_overdue} days overdue). Prepare MSMED Act Section 18 Demand Notice."
                    channel = 'REGISTERED_POST'
                    is_aggressive = True
                    effort = 2
                    return_weight = (amount / 100000.0) * 2.5
                else:
                    action_type = 'CFO_ESCALATION'
                    stage = 'Stage 3 — Finance Escalation'
                    reason = f"Receivable is {days_overdue} days past contractual due date. Direct outreach to Head of Accounts."
                    channel = 'CALL'
                    is_aggressive = False
                    effort = 1
                    return_weight = (amount / 100000.0) * 1.8
            # Rule 3: Overdue 1 to 30 days
            elif days_overdue > 0:
                action_type = 'FORMAL_REMINDER'
                stage = 'Stage 2 — Courteous Follow-up'
                reason = f"Invoice overdue by {days_overdue} days. Send statement of accounts and payment confirmation request."
                channel = 'EMAIL'
                is_aggressive = False
                effort = 1
                return_weight = (amount / 100000.0) * 1.5
            # Rule 4: CPSE / TReDS eligible
            elif buyer.is_cpse and amount >= 50000:
                action_type = 'TREDS_LISTING'
                stage = 'Liquidity Optimization'
                reason = "Buyer is a CPSE registered on TReDS. Receivable eligible for competitive auction factoring."
                channel = 'PORTAL'
                is_aggressive = False
                effort = 1
                return_weight = (amount / 100000.0) * 1.4
            else:
                # Due shortly (within 7 days)
                days_left = (due_date - today).days
                if 0 <= days_left <= 7:
                    action_type = 'COMMERCIAL_CHECKIN'
                    stage = 'Stage 1 — Due Date Alignment'
                    reason = f"Invoice maturing in {days_left} days. Confirm bill processing with buyer payables desk."
                    channel = 'EMAIL'
                    is_aggressive = False
                    effort = 1
                    return_weight = (amount / 100000.0) * 1.1
                else:
                    continue

            candidate_actions.append({
                'invoice_id': inv.invoice_id,
                'invoice_number': inv.invoice_number,
                'buyer_name': buyer.canonical_name,
                'amount': amount,
                'action_type': action_type,
                'stage': stage,
                'reason': reason,
                'channel': channel,
                'is_aggressive': is_aggressive,
                'effort': effort,
                'expected_return': return_weight,
                'existing_action': existing
            })

        # Run OR-Tools Optimization to schedule top actions within capacity limit (e.g. 5)
        optimized = self.optimizer.optimize_action_schedule(candidate_actions, max_daily_capacity=5)
        return optimized

    def approve_action(self, action_id: str, approved_by_user_id: str) -> ActionItem:
        """
        Human Approval Gateway:
        No external action occurs without explicit human authorization.
        """
        action = self.db.query(ActionItem).filter(ActionItem.action_id == action_id).first()
        if not action:
            raise ValueError(f"Action {action_id} not found")

        action.status = 'APPROVED'
        action.approved_by = approved_by_user_id
        action.approved_at = utc_now()
        
        self.identity_service.log_audit_event(
            tenant_id=action.tenant_id,
            user_id=approved_by_user_id,
            action='ACTION_APPROVED',
            object_type='ActionItem',
            object_id=action.action_id,
            after_state=f"Approved action '{action.action_type}' for Invoice {action.invoice_id}"
        )
        self.db.commit()
        return action

    def record_action_outcome(
        self,
        action_id: str,
        outcome: str, # PAYMENT_RECEIVED, PROMISE_TO_PAY, DISPUTED, NO_RESPONSE
        amount_recovered: Optional[float] = None,
        feedback_notes: Optional[str] = None
    ) -> ActionItem:
        """
        Intervention Learning Loop:
        Record actual outcome to evaluate action effectiveness.
        """
        action = self.db.query(ActionItem).filter(ActionItem.action_id == action_id).first()
        if not action:
            raise ValueError(f"Action {action_id} not found")

        action.status = 'EXECUTED'
        action.executed_at = utc_now()
        action.outcome = outcome
        action.amount_recovered = amount_recovered
        action.feedback_notes = feedback_notes
        if action.approved_at:
            action.days_to_outcome = (date.today() - action.approved_at.date()).days

        self.identity_service.log_audit_event(
            tenant_id=action.tenant_id,
            user_id=action.approved_by,
            action='ACTION_OUTCOME_RECORDED',
            object_type='ActionItem',
            object_id=action.action_id,
            after_state=f"Outcome: {outcome}, Recovered: ₹{amount_recovered or 0:,.2f}"
        )
        self.db.commit()
        return action
