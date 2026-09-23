"""
ML Delay Classifier with SHAP Feature Attribution
Trains and serves calibrated tree model (XGBoost / RandomForest) to estimate P(Late)
and calculates TreeSHAP feature importances mapped to business prediction drivers.
"""

from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import xgboost as xgb
import shap

FEATURE_COLUMNS = [
    'amount', 'agreed_term', 'history_depth', 'buyer_is_cpse',
    'buyer_median_days', 'buyer_variability', 'buyer_delay_rate',
    'open_invoices_count', 'concentration_ratio', 'acceptance_delay',
    'has_po', 'has_grn', 'ocr_confidence'
]

class DelayPredictionModel:
    def __init__(self):
        self.model = xgb.XGBClassifier(
            n_estimators=60,
            max_depth=3,
            learning_rate=0.08,
            random_state=42,
            eval_metric='logloss'
        )
        self.explainer = None
        self._is_trained = False

    def train_baseline(self, X: pd.DataFrame, y: np.ndarray):
        """Train model and build SHAP explainer."""
        self.model.fit(X[FEATURE_COLUMNS], y)
        self.explainer = shap.TreeExplainer(self.model)
        self._is_trained = True

    def predict_late_probability_and_shap(self, feature_dict: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Output late probability and SHAP local explanation contributions.
        """
        if not self._is_trained:
            # Self-train on synthetic Indian MSME baseline distribution if not trained yet
            synth_X, synth_y = self._generate_synthetic_training_data()
            self.train_baseline(synth_X, synth_y)

        df = pd.DataFrame([{col: feature_dict.get(col, 0.0) for col in FEATURE_COLUMNS}])
        prob = float(self.model.predict_proba(df)[0][1])

        shap_values = self.explainer.shap_values(df)
        if isinstance(shap_values, list):
            sv = shap_values[1][0]
        else:
            sv = shap_values[0]

        drivers = []
        for col, val, shap_w in zip(FEATURE_COLUMNS, df.iloc[0], sv):
            impact = "HIGH" if abs(shap_w) > 0.15 else ("MEDIUM" if abs(shap_w) > 0.05 else "LOW")
            direction = "INCREASES_DELAY" if shap_w > 0 else "REDUCES_DELAY"
            drivers.append({
                'feature_key': col,
                'feature_value': val,
                'shap_weight': round(float(shap_w), 3),
                'impact': impact,
                'direction': direction
            })

        # Sort by absolute SHAP impact
        drivers.sort(key=lambda d: abs(d['shap_weight']), reverse=True)
        return round(prob, 3), drivers

    def _generate_synthetic_training_data(self) -> Tuple[pd.DataFrame, np.ndarray]:
        """Generate empirical synthetic training samples across regimes."""
        np.random.seed(42)
        n = 300
        amounts = np.random.lognormal(mean=12.0, sigma=0.8, size=n)
        agreed_terms = np.random.choice([30, 45, 60], size=n, p=[0.25, 0.65, 0.10])
        history_depths = np.random.randint(1, 25, size=n)
        is_cpse = np.random.choice([0, 1], size=n, p=[0.75, 0.25])
        buyer_median = agreed_terms + np.random.normal(loc=12, scale=15, size=n)
        buyer_var = np.random.uniform(3, 20, size=n)
        buyer_delays = np.clip(np.random.uniform(0.1, 0.8, size=n), 0, 1)
        open_invs = np.random.randint(0, 12, size=n)
        concs = np.random.uniform(0.05, 0.50, size=n)
        acc_delays = np.random.exponential(scale=4, size=n)
        has_pos = np.random.choice([0, 1], size=n, p=[0.1, 0.9])
        has_grns = np.random.choice([0, 1], size=n, p=[0.2, 0.8])
        ocr_confs = np.random.uniform(0.70, 0.99, size=n)

        X = pd.DataFrame({
            'amount': amounts,
            'agreed_term': agreed_terms,
            'history_depth': history_depths,
            'buyer_is_cpse': is_cpse,
            'buyer_median_days': buyer_median,
            'buyer_variability': buyer_var,
            'buyer_delay_rate': buyer_delays,
            'open_invoices_count': open_invs,
            'concentration_ratio': concs,
            'acceptance_delay': acc_delays,
            'has_po': has_pos,
            'has_grn': has_grns,
            'ocr_confidence': ocr_confs
        })

        # Ground truth delay label: delayed if delay_rate > 0.4 and not cpse or large acc delay
        y = ((buyer_delays > 0.40) & (is_cpse == 0) | (acc_delays > 10) | (concs > 0.35)).astype(int)
        return X, y
