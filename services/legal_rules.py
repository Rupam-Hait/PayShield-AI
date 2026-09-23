"""
Engine 4: Legal Payment Clock & Regulatory Rules Engine
MSMED Act 2006 (Sections 15, 16, 17, 18) Versioned Rule Implementation.
Strict guardrail: Deterministic legal logic only. Legal eligibility never comes from ML.
No hardcoded legal constants; reads from versioned rules.
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from models.rules import RuleVersion
from models.invoice import Invoice
from models.buyer import Buyer
from models.tenant import Tenant

# Default fallback rule dictionary if database rules are being seeded
DEFAULT_RULES = {
    'MSMED_ACT_SECTION_15_OUTER_LIMIT': {
        'version': '2006.1',
        'value': 45.0, # 45 days statutory outer limit
        'source': 'MSMED Act 2006, Section 15',
        'description': 'Payment period agreed between buyer and supplier shall not exceed 45 days from day of acceptance or deemed acceptance.'
    },
    'MSMED_ACT_SECTION_15_NO_AGREEMENT_LIMIT': {
        'version': '2006.1',
        'value': 15.0, # 15 days when no written agreement exists
        'source': 'MSMED Act 2006, Section 15 (Proviso)',
        'description': 'Where there is no agreement, payment must be made on or before the appointed day (15 days from acceptance).'
    },
    'MSMED_ACT_DEEMED_ACCEPTANCE_DAYS': {
        'version': '2006.1',
        'value': 15.0,
        'source': 'MSMED Act 2006, Section 2(b)',
        'description': 'Day of deemed acceptance is 15 days from delivery of goods or rendition of services if no objection is lodged in writing.'
    },
    'MSMED_ACT_SECTION_16_INTEREST_MULTIPLIER': {
        'version': '2006.1',
        'value': 3.0, # 3 times RBI bank rate
        'source': 'MSMED Act 2006, Section 16',
        'description': 'Statutory compound interest at three times the RBI bank rate compounded with monthly rests.'
    },
    'RBI_BANK_RATE_CURRENT': {
        'version': '2026.1',
        'value': 6.75, # RBI Bank Rate % per annum
        'source': 'Reserve Bank of India Monetary Policy Notification',
        'description': 'Applicable RBI Bank Rate for statutory interest calculation.'
    }
}

class LegalPaymentClockEngine:
    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
        
    def get_rule_value(self, rule_name: str) -> Dict[str, Any]:
        """Fetch active rule version from DB or fallback default."""
        if self.db:
            rule = self.db.query(RuleVersion).filter(
                RuleVersion.rule_name == rule_name,
                RuleVersion.effective_to.is_(None)
            ).first()
            if rule:
                return {
                    'version': rule.version,
                    'value': rule.numeric_value,
                    'source': rule.source,
                    'description': rule.description
                }
        return DEFAULT_RULES.get(rule_name, {'version': '2006.1', 'value': 0.0, 'source': 'MSMED Act 2006', 'description': ''})

    def evaluate_enterprise_eligibility(self, tenant: Tenant) -> Dict[str, Any]:
        """
        Step 1 in deterministic legal pipeline:
        Enterprise classification -> Activity classification -> Transaction eligibility
        """
        is_micro_small = tenant.enterprise_type.upper() in ['MICRO', 'SMALL']
        is_manufacturing_or_service = tenant.activity_type.upper() in ['MANUFACTURING', 'SERVICES']
        
        # Wholesale/retail traders are eligible for Udyam registration since 2021 for priority sector lending,
        # but restricted from MSEFC arbitration under Section 18 unless specific conditions are met.
        is_msefc_eligible = is_micro_small and is_manufacturing_or_service
        
        reasons = []
        if not is_micro_small:
            reasons.append(f"Enterprise type is '{tenant.enterprise_type}'. MSMED Act Chap V protection applies primarily to Micro and Small enterprises.")
        if not is_manufacturing_or_service:
            reasons.append(f"Enterprise activity '{tenant.activity_type}' may face MSEFC jurisdictional objection under Office Memorandum 1/4(1)/2021-P&G/Policy.")
            
        return {
            'is_eligible': is_msefc_eligible,
            'is_micro_small': is_micro_small,
            'activity_type': tenant.activity_type,
            'enterprise_type': tenant.enterprise_type,
            'udyam_id': tenant.udyam_id,
            'reasons': reasons,
            'pathway': 'MSEFC_STATUTORY' if is_msefc_eligible else 'COMMERCIAL_ODR_ONLY'
        }

    def calculate_legal_payment_clock(
        self,
        invoice_date: date,
        delivery_date: Optional[date],
        acceptance_date: Optional[date],
        written_agreement: bool,
        agreed_term_days: int,
        as_of_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Deterministic Legal Payment Clock calculation.
        Never computes due date simply as invoice_date + 45.
        Rules:
        1. If delivery date is provided but no formal acceptance, deemed acceptance occurs 15 days post-delivery.
        2. Effective acceptance date = acceptance_date or deemed_acceptance or delivery_date or invoice_date.
        3. If written agreement exists, contractual due date = effective_acceptance + agreed_term_days.
           Statutory outer limit is effective_acceptance + 45 days.
           Statutory due date = min(contractual_due_date, statutory_outer_limit).
        4. If NO written agreement exists, statutory due date = effective_acceptance + 15 days.
        """
        if as_of_date is None:
            as_of_date = date.today()
            
        outer_limit_rule = self.get_rule_value('MSMED_ACT_SECTION_15_OUTER_LIMIT')
        no_agreement_rule = self.get_rule_value('MSMED_ACT_SECTION_15_NO_AGREEMENT_LIMIT')
        deemed_rule = self.get_rule_value('MSMED_ACT_DEEMED_ACCEPTANCE_DAYS')
        interest_mult_rule = self.get_rule_value('MSMED_ACT_SECTION_16_INTEREST_MULTIPLIER')
        bank_rate_rule = self.get_rule_value('RBI_BANK_RATE_CURRENT')
        
        deemed_days = int(deemed_rule['value'])
        outer_limit_days = int(outer_limit_rule['value'])
        no_agree_days = int(no_agreement_rule['value'])
        
        # Deemed acceptance resolution
        deemed_date = None
        if delivery_date:
            deemed_date = delivery_date + timedelta(days=deemed_days)
            
        if acceptance_date:
            base_clock_date = acceptance_date
            acceptance_type = "EXPRESS_ACCEPTANCE"
        elif deemed_date:
            base_clock_date = deemed_date
            acceptance_type = "DEEMED_ACCEPTANCE"
        elif delivery_date:
            base_clock_date = delivery_date
            acceptance_type = "DELIVERY_DATE_PROXY"
        else:
            base_clock_date = invoice_date
            acceptance_type = "INVOICE_DATE_FALLBACK"

        # Contractual vs Statutory Due Date
        if written_agreement and agreed_term_days > 0:
            contractual_due_date = base_clock_date + timedelta(days=agreed_term_days)
            statutory_outer_limit = base_clock_date + timedelta(days=outer_limit_days)
            # Cap at statutory outer limit of 45 days under Section 15
            statutory_due_date = min(contractual_due_date, statutory_outer_limit)
            is_contract_capped_by_statute = agreed_term_days > outer_limit_days
        else:
            # Under Section 15 proviso, where there is no agreement, payment due on or before appointed day (15 days)
            contractual_due_date = base_clock_date + timedelta(days=no_agree_days)
            statutory_outer_limit = base_clock_date + timedelta(days=no_agree_days)
            statutory_due_date = contractual_due_date
            is_contract_capped_by_statute = False

        # Status and Days Calculation
        days_since_invoice = (as_of_date - invoice_date).days
        days_from_base = (as_of_date - base_clock_date).days
        days_overdue_statutory = max(0, (as_of_date - statutory_due_date).days)
        days_until_statutory_breach = (statutory_due_date - as_of_date).days
        
        if as_of_date <= statutory_due_date:
            clock_status = "WITHIN_STATUTORY_LIMIT"
            status_badge = "SAFE"
        elif days_overdue_statutory <= 15:
            clock_status = "STATUTORY_OVERDUE_GRACE"
            status_badge = "WATCH"
        else:
            clock_status = "ACTIONABLE_STATUTORY_DEFAULT"
            status_badge = "HIGH RISK"

        # Statutory Interest start date = day immediately following statutory due date
        statutory_interest_start_date = statutory_due_date + timedelta(days=1)
        
        # Annual effective statutory rate = 3 * RBI Bank Rate
        rbi_bank_rate = bank_rate_rule['value']
        multiplier = interest_mult_rule['value']
        annual_statutory_interest_rate = rbi_bank_rate * multiplier
        
        return {
            'base_clock_date': base_clock_date,
            'acceptance_type': acceptance_type,
            'deemed_acceptance_date': deemed_date,
            'contractual_due_date': contractual_due_date,
            'statutory_due_date': statutory_due_date,
            'statutory_outer_limit_date': statutory_outer_limit,
            'is_contract_capped_by_statute': is_contract_capped_by_statute,
            'statutory_interest_start_date': statutory_interest_start_date,
            'days_since_invoice': days_since_invoice,
            'days_from_acceptance': days_from_base,
            'days_overdue_statutory': days_overdue_statutory,
            'days_until_statutory_breach': days_until_statutory_breach,
            'clock_status': clock_status,
            'status_badge': status_badge,
            'rule_version': outer_limit_rule['version'],
            'rule_source': outer_limit_rule['source'],
            'rbi_bank_rate': rbi_bank_rate,
            'statutory_interest_rate_pa': annual_statutory_interest_rate
        }

    def calculate_statutory_interest(
        self,
        principal_amount: float,
        statutory_due_date: date,
        as_of_date: Optional[date] = None,
        annual_rate: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Section 16: Compound interest with monthly rests at 3x RBI bank rate.
        A = P * (1 + r/12)^(months)
        """
        if as_of_date is None:
            as_of_date = date.today()
            
        if as_of_date <= statutory_due_date:
            return {
                'principal': principal_amount,
                'interest_accrued': 0.0,
                'total_claimable': principal_amount,
                'days_default': 0,
                'monthly_rate': 0.0,
                'annual_rate': 0.0
            }
            
        if annual_rate is None:
            interest_mult = self.get_rule_value('MSMED_ACT_SECTION_16_INTEREST_MULTIPLIER')['value']
            bank_rate = self.get_rule_value('RBI_BANK_RATE_CURRENT')['value']
            annual_rate = bank_rate * interest_mult # e.g. 6.75 * 3 = 20.25% p.a.
            
        days_default = (as_of_date - statutory_due_date).days
        months_fraction = days_default / 30.4375
        monthly_rate = (annual_rate / 100.0) / 12.0
        
        # Monthly compounding: P * (1 + i)^n - P
        total_amount = principal_amount * ((1.0 + monthly_rate) ** months_fraction)
        interest_accrued = round(total_amount - principal_amount, 2)
        
        return {
            'principal': principal_amount,
            'interest_accrued': interest_accrued,
            'total_claimable': round(principal_amount + interest_accrued, 2),
            'days_default': days_default,
            'monthly_rate': round(monthly_rate * 100, 3),
            'annual_rate': annual_rate,
            'statutory_basis': 'MSMED Act Section 16 (3x RBI Bank Rate with monthly rests)'
        }
