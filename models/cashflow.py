from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, DateTime, Date, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base, utc_now, generate_uuid

class CashFlow(Base):
    __tablename__ = 'cashflows'
    
    cashflow_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Type: 'INFLOW', 'OUTFLOW'
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    # Category: 'RECEIPT', 'PAYROLL', 'VENDOR', 'TAX', 'EMI', 'RENT', 'OPERATING'
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")
    
    # Certainty: 'DETERMINISTIC', 'CONTRACTUAL', 'ESTIMATED', 'SCENARIO'
    certainty: Mapped[str] = mapped_column(String(32), default="DETERMINISTIC")
    source: Mapped[str] = mapped_column(String(64), default="MANUAL_SCHEDULE") # ERP, BANK_AA_SANDBOX, MANUAL_SCHEDULE
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
