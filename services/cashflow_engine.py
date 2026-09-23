"""
Engine 8: CashFlow Digital Twin Engine
Simulates cash inflows, deterministic outflows, obligations, and survival probabilities via Monte Carlo.
Computes Cash Survival Date: earliest future date where P(cash < safety_threshold) >= threshold_prob.
Strict Guardrail: Outputs liquidity-gap range, NEVER loan approval or lender advice.
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from models.cashflow import CashFlow
from models.invoice import Invoice
from models.buyer import Buyer
from services.survival_engine import SurvivalAnalysisEngine

class CashFlowDigitalTwin:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.survival_engine = SurvivalAnalysisEngine(db_session)

    def run_monte_carlo_simulation(
        self,
        tenant_id: str,
        starting_cash: float = 1250000.0, # Default ₹12.5 Lakhs
        safety_threshold: float = 500000.0, # ₹5 Lakhs minimum safety buffer
        threshold_probability: float = 0.60, # 60% probability of breach triggers survival warning
        simulation_weeks: int = 10,
        n_simulations: int = 500,
        scenario_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation across 70 days.
        Combines deterministic obligations (payroll, GST, rent, EMI) and probabilistic receivables.
        Supports scenario overrides (e.g. buyer delay +30 days).
        """
        today = date.today()
        num_days = simulation_weeks * 7
        date_range = [today + timedelta(days=i) for i in range(num_days)]

        # 1. Fetch scheduled cashflows (obligations & recurring outflows)
        scheduled_flows = self.db.query(CashFlow).filter(
            CashFlow.tenant_id == tenant_id,
            CashFlow.date >= today,
            CashFlow.date <= date_range[-1]
        ).all()

        daily_outflows = {d: 0.0 for d in date_range}
        for flow in scheduled_flows:
            if flow.type == 'OUTFLOW' and flow.date in daily_outflows:
                daily_outflows[flow.date] += flow.amount

        # Add standard recurring MSME obligations if sparse in database:
        # e.g., Payroll on 1st of month (₹4.5L), GST on 20th (₹2.2L), EMI on 10th (₹1.1L)
        for d in date_range:
            if d.day == 1 and daily_outflows[d] == 0.0:
                daily_outflows[d] += 450000.0 # Monthly payroll
            elif d.day == 20 and daily_outflows[d] == 0.0:
                daily_outflows[d] += 220000.0 # GST return liability
            elif d.day == 10 and daily_outflows[d] == 0.0:
                daily_outflows[d] += 110000.0 # Working capital loan EMI

        # 2. Fetch open receivables
        open_invoices = self.db.query(Invoice).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.status.in_(['ISSUED', 'DELIVERED', 'ACCEPTED', 'PARTIALLY_PAID'])
        ).all()

        # Inflow simulation matrix: (n_simulations, num_days)
        simulated_inflows = np.zeros((n_simulations, num_days))

        for inv in open_invoices:
            # Check for scenario overrides (e.g. buyer delayed by extra days)
            extra_delay = 0
            if scenario_overrides and 'delayed_buyer_id' in scenario_overrides:
                if inv.buyer_id == scenario_overrides['delayed_buyer_id']:
                    extra_delay = int(scenario_overrides.get('extra_delay_days', 0))

            # Get survival parameters
            surv = self.survival_engine.fit_and_predict(
                buyer_id=inv.buyer_id,
                invoice_amount=inv.amount,
                agreed_term=inv.agreed_term_days + extra_delay,
                invoice_date=inv.invoice_date,
                as_of_date=today,
                is_cpse=inv.buyer.is_cpse
            )

            # Sample payment arrival day for each simulation path using lognormal/gamma distribution
            p50_days = surv['p50_days'] + extra_delay
            p90_days = surv['p90_days'] + extra_delay
            std_est = max(3, (p90_days - p50_days) / 1.645)

            # Sample days from invoice date
            sampled_durations = np.random.normal(loc=p50_days, scale=std_est, size=n_simulations)

            for sim_idx in range(n_simulations):
                arr_day_offset = int(sampled_durations[sim_idx])
                pay_date = inv.invoice_date + timedelta(days=arr_day_offset)
                if today <= pay_date <= date_range[-1]:
                    day_idx = (pay_date - today).days
                    if 0 <= day_idx < num_days:
                        simulated_inflows[sim_idx, day_idx] += inv.outstanding_amount

        # 3. Simulate cumulative cash balance across days
        outflow_vec = np.array([daily_outflows[d] for d in date_range])
        cash_matrix = np.zeros((n_simulations, num_days))

        for sim_idx in range(n_simulations):
            running_cash = starting_cash
            for day_idx in range(num_days):
                running_cash += simulated_inflows[sim_idx, day_idx] - outflow_vec[day_idx]
                cash_matrix[sim_idx, day_idx] = running_cash

        # 4. Statistical trajectories across days
        p10_cash = np.percentile(cash_matrix, 10, axis=0) # Conservative scenario
        p50_cash = np.percentile(cash_matrix, 50, axis=0) # Median trajectory
        p90_cash = np.percentile(cash_matrix, 90, axis=0) # Favorable scenario

        # 5. Calculate Cash Survival Date
        # Earliest date where P(cash < safety_threshold) >= threshold_probability
        cash_survival_date = None
        cash_survival_days = None
        min_balance = float(np.min(p10_cash))

        for day_idx in range(num_days):
            prob_breach = np.mean(cash_matrix[:, day_idx] < safety_threshold)
            if prob_breach >= threshold_probability:
                cash_survival_date = date_range[day_idx]
                cash_survival_days = day_idx
                break

        # 6. Calculate Liquidity Gap Range
        # Never "Loan approved" - strictly potential financing need range
        if min_balance < safety_threshold:
            gap_lower = max(0.0, safety_threshold - float(np.min(p50_cash)))
            gap_upper = max(0.0, safety_threshold - min_balance)
            # Format in Lakhs
            gap_lower_lakhs = round(gap_lower / 100000.0, 1)
            gap_upper_lakhs = round(gap_upper / 100000.0, 1)
            liquidity_gap_text = f"₹{gap_lower_lakhs}L — ₹{gap_upper_lakhs}L potential financing need — review options"
            status_badge = "HIGH RISK" if cash_survival_days and cash_survival_days < 30 else "WATCH"
        else:
            liquidity_gap_text = "Zero immediate liquidity deficit identified"
            status_badge = "SAFE"

        # Trajectory points sampled every 5 days for clean server-rendered table/chart
        trajectory_points = []
        for i in range(0, num_days, 7):
            trajectory_points.append({
                'date': date_range[i].strftime('%d %b'),
                'day_num': i,
                'p10_cash': round(float(p10_cash[i]), 0),
                'p50_cash': round(float(p50_cash[i]), 0),
                'p90_cash': round(float(p90_cash[i]), 0),
                'safety_threshold': safety_threshold
            })

        return {
            'starting_cash': starting_cash,
            'safety_threshold': safety_threshold,
            'threshold_probability': threshold_probability,
            'cash_survival_date': cash_survival_date,
            'cash_survival_days': cash_survival_days,
            'min_expected_balance': min_balance,
            'liquidity_gap_text': liquidity_gap_text,
            'status_badge': status_badge,
            'total_open_receivables': sum(i.outstanding_amount for i in open_invoices),
            'trajectory_points': trajectory_points,
            'disclaimer': "Simulated impact based on Monte Carlo stochastic model; real-world cash flow subject to operational execution."
        }
