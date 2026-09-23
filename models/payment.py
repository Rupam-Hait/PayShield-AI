from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, DateTime, Date, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base, utc_now, generate_uuid

class Payment(Base):
    __tablename__ = 'payments'
    
    payment_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    invoice_id: Mapped[str] = mapped_column(String(64), ForeignKey('invoices.invoice_id'), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    reference: Mapped[str] = mapped_column(String(128), default="NEFT/RTGS")
    source: Mapped[str] = mapped_column(String(64), default="MANUAL") # BANK_FEED, ERP, MANUAL, SANDBOX_AA
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    invoice = relationship("Invoice", back_populates="payments")
