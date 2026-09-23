from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, Text, Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base, utc_now, generate_uuid

class Buyer(Base):
    __tablename__ = 'buyers'
    
    buyer_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gstin: Mapped[str] = mapped_column(String(15), nullable=False)
    buyer_type: Mapped[str] = mapped_column(String(64), default="PRIVATE_CORP") # CPSE, STATE_PSU, PRIVATE_CORP, LISTED, MULTINATIONAL
    is_cpse: Mapped[bool] = mapped_column(Boolean, default=False)
    turnover_exceeds_500cr: Mapped[bool] = mapped_column(Boolean, default=False) # For TReDS mandate
    treds_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    industry: Mapped[str] = mapped_column(String(128), default="Automotive & Engineering")
    location: Mapped[str] = mapped_column(String(128), default="Mumbai, Maharashtra")
    standard_payment_terms_days: Mapped[int] = mapped_column(default=45)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="buyers")
    invoices = relationship("Invoice", back_populates="buyer", cascade="all, delete-orphan")
