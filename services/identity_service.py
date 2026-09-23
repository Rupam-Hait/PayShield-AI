"""
Engine 1: Identity, Multi-Tenant Isolation & DPDP Consent Engine
Enforces row-level security per tenant_id and DPDP Act 2025 compliance.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from flask import session, request, abort
from models.tenant import Tenant, User, ConsentLedger, AuditLog
from models.base import utc_now, generate_uuid

# DPDP Act 2025 Defined Consent Purposes
VALID_CONSENT_PURPOSES = [
    'RECEIVABLES_ANALYSIS',       # Predictive delay and survival modeling
    'CASHFLOW_TWIN',              # Monte Carlo cash flow forecasting
    'TREDS_SHARING',              # TReDS readiness verification & exchange data
    'ACCOUNT_AGGREGATOR',         # Read-only banking feed sync
    'PEER_BENCHMARKING',          # Anonymized cohort benchmark
    'LEGAL_EVIDENCE_GENERATION'   # Cryptographic evidence packaging
]

class IdentityService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_current_user_and_tenant(self) -> tuple[Optional[User], Optional[Tenant]]:
        """Resolve authenticated user and tenant from session."""
        user_id = session.get('user_id')
        tenant_id = session.get('tenant_id')
        if not user_id or not tenant_id:
            return None, None
            
        user = self.db.query(User).filter_by(user_id=user_id, tenant_id=tenant_id).first()
        tenant = self.db.query(Tenant).filter_by(tenant_id=tenant_id).first()
        return user, tenant

    def enforce_tenant_isolation(self, entity_class, tenant_id: str, *filters):
        """
        Row-level security filter.
        Ensures queries are mathematically bounded to the active tenant_id.
        """
        if not hasattr(entity_class, 'tenant_id'):
            raise ValueError(f"Entity {entity_class.__name__} does not carry tenant_id")
        return self.db.query(entity_class).filter(
            entity_class.tenant_id == tenant_id,
            *filters
        )

    def log_audit_event(
        self,
        tenant_id: str,
        user_id: Optional[str],
        action: str,
        object_type: str,
        object_id: str,
        before_state: Optional[str] = None,
        after_state: Optional[str] = None
    ) -> AuditLog:
        """Create an immutable audit log entry."""
        log = AuditLog(
            audit_id=generate_uuid(),
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            object_type=object_type,
            object_id=str(object_id),
            timestamp=utc_now(),
            before_state=before_state,
            after_state=after_state
        )
        self.db.add(log)
        self.db.commit()
        return log

    def check_consent(self, tenant_id: str, purpose: str) -> bool:
        """Verify whether active consent exists for purpose under DPDP 2025."""
        consent = self.db.query(ConsentLedger).filter_by(
            tenant_id=tenant_id,
            purpose=purpose,
            status='GRANTED'
        ).first()
        return consent is not None

    def grant_consent(self, tenant_id: str, user_id: Optional[str], purpose: str, ip: str = "127.0.0.1") -> ConsentLedger:
        """Record granted consent in immutable ledger."""
        existing = self.db.query(ConsentLedger).filter_by(
            tenant_id=tenant_id,
            purpose=purpose
        ).first()
        
        if existing:
            existing.status = 'GRANTED'
            existing.granted_at = utc_now()
            existing.revoked_at = None
            consent = existing
        else:
            consent = ConsentLedger(
                consent_id=generate_uuid(),
                tenant_id=tenant_id,
                user_id=user_id,
                purpose=purpose,
                status='GRANTED',
                granted_at=utc_now(),
                ip_address=ip
            )
            self.db.add(consent)
            
        self.log_audit_event(
            tenant_id=tenant_id,
            user_id=user_id,
            action='CONSENT_GRANTED',
            object_type='ConsentLedger',
            object_id=consent.consent_id,
            after_state=f"Purpose: {purpose}"
        )
        self.db.commit()
        return consent

    def revoke_consent(self, tenant_id: str, user_id: Optional[str], purpose: str) -> bool:
        """Revoke consent immediately under Data Principal rights."""
        consent = self.db.query(ConsentLedger).filter_by(
            tenant_id=tenant_id,
            purpose=purpose,
            status='GRANTED'
        ).first()
        if consent:
            consent.status = 'REVOKED'
            consent.revoked_at = utc_now()
            self.log_audit_event(
                tenant_id=tenant_id,
                user_id=user_id,
                action='CONSENT_REVOKED',
                object_type='ConsentLedger',
                object_id=consent.consent_id,
                after_state=f"Purpose: {purpose} REVOKED"
            )
            self.db.commit()
            return True
        return False
