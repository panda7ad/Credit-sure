import json
import hashlib
import logging
import math

import joblib
import pandas as pd

from config import MODELS
from src.features import FEATURES, engineer


class CreditModel:
    def __init__(self):
        self.path = MODELS / "credit_model.joblib"
        self.meta_path = MODELS / "metadata.json"
        self.model = None
        self.meta = {}
        self.version = "unavailable"
        self.reload()

    def reload(self):
        self.model = None
        manifest_path = self.path.parent / "manifest.json"
        try:
            if not manifest_path.exists():
                logging.getLogger("creditsure").warning("model_manifest_missing")
                return
            manifest = json.loads(manifest_path.read_text())
            for path in (self.path, self.meta_path):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest != manifest.get(path.name):
                    raise ValueError("Model artifact integrity failed")
            self.version = manifest["credit_model.joblib"]
            self.meta = json.loads(self.meta_path.read_text())
            self.model = joblib.load(self.path)  # Only after verifying trusted deployment manifest.
            estimator = self.model.named_steps.get("model")
            if estimator is not None and "n_jobs" in estimator.get_params():
                estimator.set_params(n_jobs=2)
        except Exception as error:
            logging.getLogger("creditsure").error("model_load_failed type=%s", type(error).__name__)
            self.model = None

    def predict(self, payload):
        if self.model is None:
            raise RuntimeError("Model not trained. Run: python -m src.train")

        row = pd.DataFrame([{key: payload.get(key) for key in FEATURES}]).replace(
            {None: float("nan")}
        )
        features = engineer(row)
        probability = float(self.model.predict_proba(features)[:, 1][0])
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise RuntimeError("Invalid model output")
        threshold = float(self.meta.get("threshold", 0.5))
        score = int(round(300 + 600 * (1 - probability)))

        if probability < threshold * 0.55:
            risk_band = "LOW"
        elif probability < threshold:
            risk_band = "MEDIUM"
        else:
            risk_band = "HIGH"

        factors = []
        if (
            payload.get("on_time_payment_ratio") is not None
            and payload["on_time_payment_ratio"] < 0.85
        ):
            factors.append("Low on-time payment ratio")
        if (
            payload.get("credit_card_utilization") is not None
            and payload["credit_card_utilization"] > 0.7
        ):
            factors.append("High revolving-credit utilization")
        if payload["loan_amount"] / max(payload["annual_income"], 1) > 0.8:
            factors.append("High loan-to-income ratio")
        if payload.get("avg_days_late") is not None and payload["avg_days_late"] > 10:
            factors.append("Frequent payment delays")
        if payload.get("prior_defaults") is not None and payload["prior_defaults"] > 0:
            factors.append("Adverse prior application/credit history")
        if not factors:
            factors.append("No clear risk signal was identified among the available inputs")

        return {
            "default_probability": round(probability, 4),
            "repayment_probability": round(1 - probability, 4),
            "credit_score": score,
            "risk_band": risk_band,
            "threshold": threshold,
            "key_factors": factors[:4],
            "model": self.meta.get("best_model", "unknown"),
        }
