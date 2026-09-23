from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, DateTime, Date, Text, Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base, utc_now, generate_uuid

class Invoice(Base):
    __tablename__ = 'invoices'
    
    invoice_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    buyer_id: Mapped[str] = mapped_column(String(64), ForeignKey('buyers.buyer_id'), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    acceptance_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    deemed_acceptance_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    written_agreement_exists: Mapped[bool] = mapped_column(Boolean, default=True)
    agreed_term_days: Mapped[int] = mapped_column(default=45)
    contract_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    statutory_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    status: Mapped[str] = mapped_column(String(32), default="ISSUED") # ISSUED, DELIVERED, ACCEPTED, PARTIALLY_PAID, PAID, OVERDUE, DISPUTED
    goods_services_type: Mapped[str] = mapped_column(String(32), default="GOODS") # GOODS, SERVICES
    
    po_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    grn_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    eway_bill_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Financial tracking
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    outstanding_amount: Mapped[float] = mapped_column(Float, default=0.0)
    statutory_interest_accrued: Mapped[float] = mapped_column(Float, default=0.0)
    
    confidence: Mapped[float] = mapped_column(Float, default=1.0) # Document OCR & consistency confidence (0.0 to 1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="invoices")
    buyer = relationship("Buyer", back_populates="invoices")
    events = relationship("InvoiceEvent", back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceEvent.event_date")
    documents = relationship("Document", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="invoice", cascade="all, delete-orphan")
    actions = relationship("ActionItem", back_populates="invoice", cascade="all, delete-orphan")

class InvoiceEvent(Base):
    __tablename__ = 'invoice_events'
    
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    invoice_id: Mapped[str] = mapped_column(String(64), ForeignKey('invoices.invoice_id'), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    
    # Canonical event types:
    # ISSUED, DELIVERED, ACCEPTED, REJECTED, GRN_CREATED, DUE, PART_PAYMENT, FULL_PAYMENT, CREDIT_NOTE, DISPUTE
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="MANUAL") # OCR, ERP_IMPORT, BANK_FEED, MANUAL, E_WAY_BILL
    document_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey('documents.document_id'), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    invoice = relationship("Invoice", back_populates="events")
    document = relationship("Document")

class Document(Base):
    __tablename__ = 'documents'
    
    document_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    invoice_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey('invoices.invoice_id'), nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False) # INVOICE, PO, GRN, E_WAY_BILL, PAYMENT_RECEIPT, AGREEMENT
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False) # SHA-256
    ocr_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_fields_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(32), default="VALIDATED") # VALIDATED, NEEDS_REVIEW, REJECTED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    invoice = relationship("Invoice", back_populates="documents")
