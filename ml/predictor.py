# ml/predictor.py
"""
Real-time posture predictor using trained ML model.
Loads the saved sklearn model and predicts OK/BAD from features.
"""

import pickle
import numpy as np
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger(__name__)

MODEL_PATH = Path("ml/models/posture_classifier.pkl")


class PosturePredictor:
    """Loads trained ML model and predicts posture status in real-time"""

    def __init__(self, model_path: Path = MODEL_PATH):
        self.model = None
        self.model_path = model_path
        self._load_model()

    def _load_model(self):
        if not self.model_path.exists():
            logger.warning(f"ML model not found at {self.model_path}")
            return
        try:
            with open(self.model_path, 'rb') as f:
                data = pickle.load(f)

            self.model = data['model']
            self.scaler = data['scaler']
            self.feature_names = data['feature_names']

            logger.info(f"ML model loaded from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            self.model = None

    def is_available(self) -> bool:
        return self.model is not None
        

    def predict(self, forward_shift: float, lateral_tilt: float) -> dict:
        """
        Predict posture status from current posture metrics.
        Returns dict with 'status', 'confidence', 'severity', 'method'.
        """
        if self.model is None:
            return {'status': 'OK', 'confidence': 0.0, 'severity': 0.0,
                    'method': 'unavailable'}

        try:
            shift_abs = abs(forward_shift)
            tilt_abs = abs(lateral_tilt)
            shift_x_tilt = shift_abs * tilt_abs

            features = np.array([[
                forward_shift,
                lateral_tilt,
                shift_abs,
                tilt_abs,
                shift_x_tilt,
            ]])

            features_scaled = self.scaler.transform(features)

            prediction = self.model.predict(features_scaled)[0]
            probabilities = self.model.predict_proba(features_scaled)[0]

            bad_prob = float(probabilities[1]) if len(probabilities) > 1 else 0.0
            confidence = float(max(probabilities))

            # Use the model's own trained prediction (0=OK, 1=BAD)
            status = 'BAD' if prediction == 1 else 'OK'
            severity = bad_prob * 3.0

            logger.debug(
                f"ML predict: fwd={forward_shift:.3f} tilt={lateral_tilt:.3f} "
                f"-> pred={prediction} bad_prob={bad_prob:.3f} status={status}"
            )

            return {
                'status': status,
                'confidence': round(confidence, 3),
                'severity': round(severity, 3),
                'bad_probability': round(bad_prob, 3),
                'method': 'ml',
            }

        except Exception as e:
            logger.error(f"ML prediction failed: {e}")
            return {'status': 'OK', 'confidence': 0.0, 'severity': 0.0,
                    'method': 'error'}