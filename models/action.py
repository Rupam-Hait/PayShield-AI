from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Float, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base, utc_now, generate_uuid

class ActionItem(Base):
    __tablename__ = 'actions'
    
    action_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    invoice_id: Mapped[str] = mapped_column(String(64), ForeignKey('invoices.invoice_id'), nullable=False)
    
    # Action types:
    # 'VERIFY_ACCEPTANCE', 'COMMERCIAL_CHECKIN', 'FORMAL_REMINDER', 'CFO_ESCALATION', 
    # 'TREDS_LISTING', 'ODR_LEGAL_NOTICE', 'DISPUTE_RECONCILIATION'
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), default="Stage 1 - Verification")
    
    priority: Mapped[int] = mapped_column(default=1) # 1 (Highest) to 5 (Lowest)
    score: Mapped[float] = mapped_column(Float, default=0.0) # OR-Tools optimization score
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_channel: Mapped[str] = mapped_column(String(32), default="EMAIL") # EMAIL, CALL, PORTAL, REGISTERED_POST
    message_draft: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Human Approval Gateway
    # Status: 'PENDING_APPROVAL', 'APPROVED', 'EXECUTED', 'REJECTED'
    status: Mapped[str] = mapped_column(String(32), default="PENDING_APPROVAL")
    recommended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Intervention Learning Loop outcome tracking
    outcome: Mapped[Optional[str]] = mapped_column(String(64), nullable=True) # PAYMENT_RECEIVED, PROMISE_TO_PAY, DISPUTED, NO_RESPONSE
    days_to_outcome: Mapped[Optional[int]] = mapped_column(nullable=True)
    amount_recovered: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feedback_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    invoice = relationship("Invoice", back_populates="actions")
