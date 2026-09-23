"""
Engine 10: OR-Tools Receivables Action Portfolio Optimizer
Uses Google OR-Tools Integer Programming (pywraplp) to schedule and prioritize
daily recovery interventions subject to team capacity and relationship constraints.
"""

from typing import List, Dict, Any
from ortools.linear_solver import pywraplp

class ReceivablesActionOptimizer:
    def __init__(self):
        pass

    def optimize_action_schedule(
        self,
        candidate_actions: List[Dict[str, Any]],
        max_daily_capacity: int = 5,
        max_aggressive_actions: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Formulate and solve Binary Integer Linear Program:
        Maximize:
            Sum_i [ (recovery_value_i * delay_risk_i) * x_i ]
        Subject to:
            Sum_i [ effort_i * x_i ] <= max_daily_capacity
            Sum_i [ is_aggressive_i * x_i ] <= max_aggressive_actions
            x_i in {0, 1}
        """
        if not candidate_actions:
            return []

        # Create the solver with SCIP or GLOP backend
        solver = pywraplp.Solver.CreateSolver('SCIP')
        if not solver:
            # Fallback solver if SCIP not built
            solver = pywraplp.Solver.CreateSolver('CBC')
        if not solver:
            # Simple heuristic sorting fallback
            return sorted(candidate_actions, key=lambda a: a.get('expected_return', 0), reverse=True)[:max_daily_capacity]

        n = len(candidate_actions)
        x = {}
        for i in range(n):
            x[i] = solver.BoolVar(f'action_{i}')

        # Constraint 1: Team effort capacity (default effort = 1 unit per action)
        solver.Add(solver.Sum([candidate_actions[i].get('effort', 1) * x[i] for i in range(n)]) <= max_daily_capacity)

        # Constraint 2: Relationship preservation (cap aggressive escalations)
        solver.Add(solver.Sum([
            (1 if candidate_actions[i].get('is_aggressive', False) else 0) * x[i] for i in range(n)
        ]) <= max_aggressive_actions)

        # Objective: Maximize expected recovery return
        objective = solver.Objective()
        for i in range(n):
            weight = candidate_actions[i].get('expected_return', 1.0)
            objective.SetCoefficient(x[i], float(weight))
        objective.SetMaximization()

        status = solver.Solve()

        scheduled = []
        if status in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
            for i in range(n):
                if x[i].solution_value() > 0.5:
                    action = dict(candidate_actions[i])
                    action['is_selected_today'] = True
                    action['solver_status'] = 'OPTIMAL_SCHEDULED'
                    scheduled.append(action)

        # Sort selected by expected return
        scheduled.sort(key=lambda a: a.get('expected_return', 0), reverse=True)
        return scheduled
