from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, DateTime, Date, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base, utc_now, generate_uuid

class Prediction(Base):
    __tablename__ = 'predictions'
    
    prediction_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    invoice_id: Mapped[str] = mapped_column(String(64), ForeignKey('invoices.invoice_id'), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    as_of_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    # Probabilities and windows
    delay_probability: Mapped[float] = mapped_column(Float, default=0.0) # P(payment after contractual due date)
    p10_payment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    p50_payment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True) # Median expected date
    p90_payment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True) # Conservative date
    expected_delay_days: Mapped[int] = mapped_column(default=0)
    
    # Confidence & Abstention
    # Values: 'HIGH', 'MEDIUM', 'INSUFFICIENT_EVIDENCE'
    confidence: Mapped[str] = mapped_column(String(32), default="MEDIUM")
    confidence_score: Mapped[float] = mapped_column(Float, default=0.85) # 0.0 to 1.0
    is_abstained: Mapped[bool] = mapped_column(default=False)
    abstention_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prediction_basis: Mapped[str] = mapped_column(String(128), default="Consented historical MSME transaction data")
    model_version: Mapped[str] = mapped_column(String(64), default="v1.0.0-survival-cox")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    invoice = relationship("Invoice", back_populates="predictions")
    explanations = relationship("Explanation", back_populates="prediction", cascade="all, delete-orphan")

class Explanation(Base):
    __tablename__ = 'explanations'
    
    explanation_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    prediction_id: Mapped[str] = mapped_column(String(64), ForeignKey('predictions.prediction_id'), nullable=False)
    
    feature: Mapped[str] = mapped_column(String(128), nullable=False)
    # Impact: 'HIGH', 'MEDIUM', 'LOW'
    impact: Mapped[str] = mapped_column(String(32), default="MEDIUM")
    # Direction: 'INCREASES_DELAY', 'REDUCES_DELAY'
    direction: Mapped[str] = mapped_column(String(32), default="INCREASES_DELAY")
    shap_value: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_event: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    prediction = relationship("Prediction", back_populates="explanations")
