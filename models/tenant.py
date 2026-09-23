from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import generate_password_hash, check_password_hash
from models.base import Base, utc_now, generate_uuid

class Tenant(Base):
    __tablename__ = 'tenants'
    
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    udyam_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    industry: Mapped[str] = mapped_column(String(128), default="Manufacturing")
    state: Mapped[str] = mapped_column(String(64), default="Maharashtra")
    district: Mapped[str] = mapped_column(String(64), default="Pune")
    enterprise_type: Mapped[str] = mapped_column(String(32), default="Micro") # Micro, Small, Medium
    activity_type: Mapped[str] = mapped_column(String(32), default="Manufacturing") # Manufacturing, Services, Trader
    annual_turnover: Mapped[float] = mapped_column(default=35000000.0) # INR
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    buyers = relationship("Buyer", back_populates="tenant", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="tenant", cascade="all, delete-orphan")
    consents = relationship("ConsentLedger", back_populates="tenant", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="tenant", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = 'users'
    
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="PROPRIETOR") # PROPRIETOR, CFO, ACCOUNTANT, AUDITOR
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(String(20), default="+91 98200 12345")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    tenant = relationship("Tenant", back_populates="users")
    
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

class ConsentLedger(Base):
    __tablename__ = 'consent_ledger'
    
    consent_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey('users.user_id'), nullable=True)
    purpose: Mapped[str] = mapped_column(String(128), nullable=False)
    # e.g., 'RECEIVABLES_ANALYSIS', 'TREDS_SHARING', 'ACCOUNT_AGGREGATOR', 'PEER_BENCHMARKING'
    status: Mapped[str] = mapped_column(String(32), default="GRANTED") # GRANTED, REVOKED, EXPIRED
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dpdp_notice_version: Mapped[str] = mapped_column(String(32), default="2025.1")
    ip_address: Mapped[str] = mapped_column(String(45), default="127.0.0.1")
    
    tenant = relationship("Tenant", back_populates="consents")

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    
    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey('users.user_id'), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    before_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    tenant = relationship("Tenant", back_populates="audit_logs")
