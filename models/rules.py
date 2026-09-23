from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, DateTime, Date, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base, utc_now, generate_uuid

class RuleVersion(Base):
    __tablename__ = 'rule_versions'
    
    rule_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    jurisdiction: Mapped[str] = mapped_column(String(32), default="INDIA_FEDERAL")
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # e.g., 'MSMED_ACT_SECTION_15_OUTER_LIMIT', 'MSMED_ACT_SECTION_16_INTEREST_RATE', 'DEEMED_ACCEPTANCE_WINDOW'
    version: Mapped[str] = mapped_column(String(32), default="2006.1")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True) # Null means currently active
    source: Mapped[str] = mapped_column(String(255), default="MSMED Act 2006 Section 15/16")
    
    # Numerical or logical value
    numeric_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True) # DAYS, PERCENT_PER_ANNUM, MULTIPLIER
    description: Mapped[str] = mapped_column(Text, default="")
    logic_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
