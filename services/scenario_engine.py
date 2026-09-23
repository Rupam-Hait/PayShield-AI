"""
Engine 9: Rescue / What-If Scenario Simulator
Executes full server-side dynamic recalculation for hypothetical buyer delay,
dispute, or partial payment scenarios.
"""

from datetime import date, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from models.buyer import Buyer
from models.invoice import Invoice
from services.cashflow_engine import CashFlowDigitalTwin

class ScenarioSimulator:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.cashflow_twin = CashFlowDigitalTwin(db_session)

    def simulate_rescue_scenario(
        self,
        tenant_id: str,
        delayed_buyer_id: Optional[str] = None,
        extra_delay_days: int = 30,
        starting_cash: float = 1250000.0,
        safety_threshold: float = 500000.0
    ) -> Dict[str, Any]:
        """
        Run side-by-side comparison:
        1. Baseline Simulation (Current state)
        2. Stress Scenario Simulation (with hypothetical delays applied)
        Returns recalculated survival date, funding gap, and delta impact.
        """
        # Baseline simulation
        baseline = self.cashflow_twin.run_monte_carlo_simulation(
            tenant_id=tenant_id,
            starting_cash=starting_cash,
            safety_threshold=safety_threshold,
            scenario_overrides=None
        )

        scenario_buyer = None
        if delayed_buyer_id:
            scenario_buyer = self.db.query(Buyer).filter(
                Buyer.buyer_id == delayed_buyer_id,
                Buyer.tenant_id == tenant_id
            ).first()

        # Stressed simulation
        scenario_overrides = {
            'delayed_buyer_id': delayed_buyer_id,
            'extra_delay_days': extra_delay_days
        } if delayed_buyer_id else None

        stressed = self.cashflow_twin.run_monte_carlo_simulation(
            tenant_id=tenant_id,
            starting_cash=starting_cash,
            safety_threshold=safety_threshold,
            scenario_overrides=scenario_overrides
        )

        # Delta metrics
        base_days = baseline['cash_survival_days'] or 999
        stress_days = stressed['cash_survival_days'] or 999
        days_lost = max(0, base_days - stress_days) if stress_days < 999 else 0
        liquidity_impact = max(0.0, baseline['min_expected_balance'] - stressed['min_expected_balance'])

        # Action recommendation triggered by scenario
        recommended_mitigation = []
        if stressed['status_badge'] == 'HIGH RISK':
            recommended_mitigation.append("Initiate TReDS invoice discounting immediately on eligible CPSE receivables to inject liquidity.")
            recommended_mitigation.append("Issue Stage 2 commercial follow-up to delayed buyer with delivery proof and ledger extract.")
            recommended_mitigation.append("Temporarily defer discretionary capital expenditures until cash buffer returns above ₹5 Lakhs.")
        else:
            recommended_mitigation.append("Cash runway remains resilient under this delay scenario. Maintain standard follow-up.")

        return {
            'delayed_buyer': scenario_buyer,
            'extra_delay_days': extra_delay_days,
            'baseline': baseline,
            'stressed': stressed,
            'days_lost': days_lost,
            'liquidity_impact_amount': liquidity_impact,
            'liquidity_impact_lakhs': round(liquidity_impact / 100000.0, 1),
            'recommended_mitigation': recommended_mitigation,
            'label': "Synthetic benchmark demonstrates technical feasibility; real-world validation requires consented historical MSME data."
        }
