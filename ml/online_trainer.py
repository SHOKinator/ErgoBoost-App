# ml/online_trainer.py
"""
Background model retrainer for ErgoBoost.
After a rule-based monitoring session ends, checks if enough new data
has accumulated and retrains the posture classifier in a background thread.

The retrained model is saved to disk and can be hot-swapped into
the running PosturePredictor without restarting the app.
"""

import threading
import sqlite3
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score
from sklearn.preprocessing import StandardScaler

from utils.logger import setup_logger

logger = setup_logger(__name__)

MODEL_PATH = Path("ml/models/posture_classifier.pkl")
DB_PATH = Path("data/ergoboost.db")

# Minimum new samples since last training to trigger retraining
MIN_NEW_SAMPLES = 300

# Minimum total samples needed to train a model at all
MIN_TOTAL_SAMPLES = 500

# Minimum F1 improvement to replace existing model
MIN_F1_IMPROVEMENT = -0.005  # allow slight regression (noise), block major drops


class OnlineTrainer:
    """Manages background retraining of the posture ML model."""

    def __init__(self, db_path: Path = DB_PATH, model_path: Path = MODEL_PATH):
        self.db_path = db_path
        self.model_path = model_path
        self._training_lock = threading.Lock()
        self._is_training = False

    def maybe_retrain_async(self, predictor=None):
        """
        Check if retraining is needed and run it in a background thread.
        
        Args:
            predictor: optional PosturePredictor instance to hot-swap the model into
        """
        if self._is_training:
            logger.debug("Retraining already in progress, skipping")
            return

        # Quick check: enough new data?
        if not self._should_retrain():
            return

        thread = threading.Thread(
            target=self._retrain_worker,
            args=(predictor,),
            daemon=True,
            name="MLRetrainThread"
        )
        thread.start()
        logger.info("Background model retraining started")

    def _should_retrain(self) -> bool:
        """Check if there are enough new samples to justify retraining."""
        try:
            conn = sqlite3.connect(str(self.db_path))

            # Count total posture events with rule-based labels
            total = conn.execute(
                "SELECT COUNT(*) FROM posture_events "
                "WHERE forward_shift IS NOT NULL AND lateral_tilt IS NOT NULL"
            ).fetchone()[0]

            if total < MIN_TOTAL_SAMPLES:
                logger.debug(f"Not enough total data for retraining: {total} < {MIN_TOTAL_SAMPLES}")
                conn.close()
                return False

            # Check when model was last trained
            last_trained_at = None
            if self.model_path.exists():
                try:
                    with open(self.model_path, 'rb') as f:
                        data = pickle.load(f)
                    last_trained_at = data.get('trained_at')
                    last_train_samples = data.get('train_samples', 0) + data.get('test_samples', 0)
                except Exception:
                    last_train_samples = 0
            else:
                last_train_samples = 0

            new_samples = total - last_train_samples
            logger.info(f"Retraining check: {total} total, {last_train_samples} at last training, "
                        f"{new_samples} new samples")

            conn.close()
            return new_samples >= MIN_NEW_SAMPLES

        except Exception as e:
            logger.error(f"Failed to check retraining status: {e}")
            return False

    def _retrain_worker(self, predictor=None):
        """Background worker that performs the actual retraining."""
        if not self._training_lock.acquire(blocking=False):
            return

        self._is_training = True
        try:
            logger.info("=== Background Retraining Started ===")
            start_time = datetime.now()

            # Load and merge data (same logic as train_model.py)
            df = self._load_training_data()
            if df is None or len(df) < MIN_TOTAL_SAMPLES:
                logger.warning(f"Insufficient training data: {len(df) if df is not None else 0}")
                return

            # Engineer features
            X, y, feature_names = self._engineer_features(df)

            # Load current model metrics for comparison
            old_f1 = self._get_current_model_f1()

            # Train new model
            new_model, new_scaler, new_f1 = self._train_model(X, y, feature_names)

            if new_model is None:
                logger.error("Training produced no model")
                return

            # Compare and decide whether to replace
            if old_f1 is not None and (new_f1 - old_f1) < MIN_F1_IMPROVEMENT:
                logger.info(f"New model F1={new_f1:.4f} not better than current F1={old_f1:.4f}, "
                            f"keeping current model")
                return

            # Save new model
            self._save_model(new_model, new_scaler, feature_names, new_f1,
                             len(X), old_f1)

            # Hot-swap into running predictor
            if predictor is not None:
                predictor.model = new_model
                predictor.scaler = new_scaler
                predictor.feature_names = feature_names
                logger.info("Model hot-swapped into running predictor")

            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"=== Background Retraining Complete in {elapsed:.1f}s ===")
            logger.info(f"    Old F1: {old_f1:.4f}" if old_f1 else "    Old F1: N/A (first training)")
            logger.info(f"    New F1: {new_f1:.4f}")
            logger.info(f"    Samples: {len(X)}")

        except Exception as e:
            logger.error(f"Background retraining failed: {e}", exc_info=True)
        finally:
            self._is_training = False
            self._training_lock.release()

    def _load_training_data(self) -> pd.DataFrame:
        """Load posture data from SQLite (posture-only, no eye/distance)."""
        try:
            conn = sqlite3.connect(str(self.db_path))

            posture_df = pd.read_sql_query("""
                SELECT session_id, timestamp, forward_shift, lateral_tilt,
                       severity, posture_status
                FROM posture_events
                WHERE forward_shift IS NOT NULL AND lateral_tilt IS NOT NULL
            """, conn)

            conn.close()

            logger.info(f"Loaded {len(posture_df)} posture events")

            posture_df = posture_df.dropna(subset=['forward_shift', 'lateral_tilt'])

            # Encode label
            posture_df['label'] = (posture_df['posture_status'] == 'BAD').astype(int)

            logger.info(f"Dataset: {len(posture_df)} samples "
                        f"(OK={int((posture_df['label']==0).sum())}, "
                        f"BAD={int((posture_df['label']==1).sum())})")

            return posture_df

        except Exception as e:
            logger.error(f"Failed to load training data: {e}")
            return None

    def _engineer_features(self, df: pd.DataFrame) -> tuple:
        """Create feature matrix (posture-only features)."""
        df = df.copy()
        df['shift_abs'] = df['forward_shift'].abs()
        df['tilt_abs'] = df['lateral_tilt'].abs()
        df['shift_x_tilt'] = df['shift_abs'] * df['tilt_abs']

        features = [
            'forward_shift', 'lateral_tilt',
            'shift_abs', 'tilt_abs', 'shift_x_tilt',
        ]

        X = df[features].values
        y = df['label'].values

        return X, y, features

    def _train_model(self, X, y, feature_names):
        """Train a GradientBoosting classifier and return (model, scaler, f1)."""
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Train GradientBoosting (best model from original training)
            model = GradientBoostingClassifier(
                n_estimators=100, max_depth=6, learning_rate=0.1,
                min_samples_leaf=10, random_state=42
            )
            model.fit(X_train_scaled, y_train)

            y_pred = model.predict(X_test_scaled)
            f1 = f1_score(y_test, y_pred, zero_division=0)

            logger.info(f"Retrained model F1: {f1:.4f} "
                        f"(train={len(X_train)}, test={len(X_test)})")

            return model, scaler, f1

        except Exception as e:
            logger.error(f"Model training failed: {e}")
            return None, None, 0.0

    def _get_current_model_f1(self) -> float:
        """Load the F1 score of the current saved model."""
        if not self.model_path.exists():
            return None
        try:
            with open(self.model_path, 'rb') as f:
                data = pickle.load(f)
            metrics = data.get('metrics', {})
            return metrics.get('f1', None)
        except Exception:
            return None

    def _save_model(self, model, scaler, feature_names, f1,
                    sample_count, old_f1):
        """Save the retrained model to disk."""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        train_count = int(sample_count * 0.8)
        test_count = sample_count - train_count

        with open(self.model_path, 'wb') as f:
            pickle.dump({
                'model': model,
                'scaler': scaler,
                'feature_names': feature_names,
                'model_name': 'gradient_boosting',
                'trained_at': datetime.now().isoformat(),
                'metrics': {'f1': f1},
                'train_samples': train_count,
                'test_samples': test_count,
                'retrained': True,
                'previous_f1': old_f1,
            }, f)

        logger.info(f"Retrained model saved to {self.model_path}")
