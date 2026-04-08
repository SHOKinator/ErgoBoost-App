# ml/train_model.py
"""
ErgoBoost ML Training Pipeline.

Trains a posture classifier on collected data.
Uses scikit-learn with GroupKFold validation by session_id.

Features: forward_shift, lateral_tilt, shift_abs, tilt_abs, shift_x_tilt
Label: posture_status (OK=0, BAD=1)

Usage:
    python -m ml.train_model
    python -m ml.train_model --db data/ergoboost.db --output ml/models
"""

import sys
import argparse
import sqlite3
import pickle
import json
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import (
    train_test_split, cross_val_score,
    GroupKFold, GroupShuffleSplit
)
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_data(db_path: str) -> pd.DataFrame:
    """Load posture data from SQLite (only posture features, no eye/distance)"""
    conn = sqlite3.connect(db_path)

    print("Loading posture events...")
    posture_df = pd.read_sql_query("""
        SELECT session_id, timestamp, forward_shift, lateral_tilt,
               severity, posture_status
        FROM posture_events
        WHERE forward_shift IS NOT NULL AND lateral_tilt IS NOT NULL
    """, conn)

    conn.close()

    print(f"  Posture events: {len(posture_df):,}")

    # Drop rows with missing posture values
    posture_df = posture_df.dropna(subset=['forward_shift', 'lateral_tilt'])

    # Encode label
    posture_df['label'] = (posture_df['posture_status'] == 'BAD').astype(int)

    print(f"\nDataset: {len(posture_df):,} samples")
    print(f"  OK: {(posture_df['label'] == 0).sum():,} ({(posture_df['label'] == 0).mean()*100:.1f}%)")
    print(f"  BAD: {(posture_df['label'] == 1).sum():,} ({(posture_df['label'] == 1).mean()*100:.1f}%)")

    return posture_df


def engineer_features(df: pd.DataFrame) -> tuple:
    """Create feature matrix, labels, and session groups (posture-only features)"""
    df = df.copy()

    # Derived posture features
    df['shift_abs'] = df['forward_shift'].abs()
    df['tilt_abs'] = df['lateral_tilt'].abs()
    df['shift_x_tilt'] = df['shift_abs'] * df['tilt_abs']  # interaction

    features = [
        'forward_shift',
        'lateral_tilt',
        'shift_abs',
        'tilt_abs',
        'shift_x_tilt',
    ]

    X = df[features].values
    y = df['label'].values
    groups = df['session_id'].values  # for GroupKFold

    return X, y, features, groups


def train_and_evaluate(X, y, feature_names, groups, output_dir: Path):
    """Train models, evaluate with GroupKFold, save"""
    output_dir.mkdir(parents=True, exist_ok=True)

    n_sessions = len(np.unique(groups))
    print(f"\nTotal sessions: {n_sessions}")

    # Split by groups (sessions) — no session leaks between train and test
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(X, y, groups))

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    groups_train = groups[train_idx]

    train_sessions = len(np.unique(groups[train_idx]))
    test_sessions = len(np.unique(groups[test_idx]))
    print(f"Train: {len(X_train):,} samples ({train_sessions} sessions)")
    print(f"Test:  {len(X_test):,} samples ({test_sessions} sessions)")

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    results = {}

    # ===== Model 1: Random Forest =====
    print("\n--- Training Random Forest ---")
    rf = RandomForestClassifier(
        n_estimators=100, max_depth=12, min_samples_leaf=10,
        random_state=42, n_jobs=-1
    )
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)

    rf_acc = accuracy_score(y_test, y_pred_rf)
    rf_prec = precision_score(y_test, y_pred_rf, zero_division=0)
    rf_rec = recall_score(y_test, y_pred_rf, zero_division=0)
    rf_f1 = f1_score(y_test, y_pred_rf, zero_division=0)

    print(f"  Accuracy:  {rf_acc:.4f}")
    print(f"  Precision: {rf_prec:.4f}")
    print(f"  Recall:    {rf_rec:.4f}")
    print(f"  F1 Score:  {rf_f1:.4f}")

    # Random 5-fold CV (baseline)
    cv_scores = cross_val_score(rf, X_train, y_train, cv=5, scoring='f1')
    print(f"  Random CV F1:  {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

    # GroupKFold CV by session_id — proves generalization across sessions
    n_folds = min(5, n_sessions)  # can't have more folds than sessions
    if n_folds >= 2:
        gkf = GroupKFold(n_splits=n_folds)
        gkf_scores = cross_val_score(
            rf, X_train, y_train, cv=gkf, groups=groups_train, scoring='f1'
        )
        print(f"  GroupKFold CV F1 ({n_folds}-fold by session): "
              f"{gkf_scores.mean():.4f} (+/- {gkf_scores.std():.4f})")
    else:
        gkf_scores = cv_scores  # fallback
        print(f"  GroupKFold: not enough sessions ({n_sessions}), skipped")

    # Feature importance
    importances = list(zip(feature_names, rf.feature_importances_))
    importances.sort(key=lambda x: x[1], reverse=True)
    print("\n  Feature Importance:")
    for name, imp in importances:
        bar = '#' * int(imp * 50)
        print(f"    {name:25s} {imp:.4f} {bar}")

    results['random_forest'] = {
        'accuracy': rf_acc, 'precision': rf_prec,
        'recall': rf_rec, 'f1': rf_f1,
        'cv_f1_mean': cv_scores.mean(), 'cv_f1_std': cv_scores.std(),
        'group_cv_f1_mean': float(gkf_scores.mean()),
        'group_cv_f1_std': float(gkf_scores.std()),
        'group_cv_folds': n_folds,
        'confusion_matrix': confusion_matrix(y_test, y_pred_rf).tolist(),
        'feature_importance': {n: float(i) for n, i in importances},
    }

    # ===== Model 2: Gradient Boosting =====
    print("\n--- Training Gradient Boosting ---")
    gb = GradientBoostingClassifier(
        n_estimators=100, max_depth=6, learning_rate=0.1,
        min_samples_leaf=10, random_state=42
    )
    gb.fit(X_train, y_train)
    y_pred_gb = gb.predict(X_test)

    gb_acc = accuracy_score(y_test, y_pred_gb)
    gb_prec = precision_score(y_test, y_pred_gb, zero_division=0)
    gb_rec = recall_score(y_test, y_pred_gb, zero_division=0)
    gb_f1 = f1_score(y_test, y_pred_gb, zero_division=0)

    print(f"  Accuracy:  {gb_acc:.4f}")
    print(f"  Precision: {gb_prec:.4f}")
    print(f"  Recall:    {gb_rec:.4f}")
    print(f"  F1 Score:  {gb_f1:.4f}")

    # GroupKFold for GB too
    if n_folds >= 2:
        gkf_gb = GroupKFold(n_splits=n_folds)
        gkf_gb_scores = cross_val_score(
            gb, X_train, y_train, cv=gkf_gb, groups=groups_train, scoring='f1'
        )
        print(f"  GroupKFold CV F1 ({n_folds}-fold by session): "
              f"{gkf_gb_scores.mean():.4f} (+/- {gkf_gb_scores.std():.4f})")
    else:
        gkf_gb_scores = np.array([gb_f1])

    results['gradient_boosting'] = {
        'accuracy': gb_acc, 'precision': gb_prec,
        'recall': gb_rec, 'f1': gb_f1,
        'group_cv_f1_mean': float(gkf_gb_scores.mean()),
        'group_cv_f1_std': float(gkf_gb_scores.std()),
        'confusion_matrix': confusion_matrix(y_test, y_pred_gb).tolist(),
    }

    # ===== Pick best model =====
    best_name = 'random_forest' if rf_f1 >= gb_f1 else 'gradient_boosting'
    best_model = rf if rf_f1 >= gb_f1 else gb
    print(f"\n=== Best Model: {best_name} (F1={results[best_name]['f1']:.4f}) ===")

    # ===== Summary: Random CV vs GroupKFold ====
    print(f"\n{'='*60}")
    print(f"  GENERALIZATION CHECK (GroupKFold by session_id)")
    print(f"{'='*60}")
    print(f"  Random Forest:")
    print(f"    Random 5-fold CV F1:     {cv_scores.mean():.4f}")
    print(f"    GroupKFold CV F1:         {gkf_scores.mean():.4f}")
    delta_rf = abs(cv_scores.mean() - gkf_scores.mean())
    print(f"    Delta:                   {delta_rf:.4f} "
          f"{'✓ Model generalizes!' if delta_rf < 0.02 else '⚠ Possible session overfitting'}")
    print(f"  Gradient Boosting:")
    print(f"    GroupKFold CV F1:         {gkf_gb_scores.mean():.4f}")
    print(f"{'='*60}")

    # ===== Save model =====
    model_path = output_dir / "posture_classifier.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump({
            'model': best_model,
            'scaler': scaler,
            'feature_names': feature_names,
            'model_name': best_name,
            'trained_at': datetime.now().isoformat(),
            'metrics': results[best_name],
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'train_sessions': train_sessions,
            'test_sessions': test_sessions,
        }, f)
    print(f"Model saved to: {model_path}")

    # ===== Save report =====
    report_path = output_dir / "training_report.json"
    report = {
        'trained_at': datetime.now().isoformat(),
        'dataset_size': len(X_train) + len(X_test),
        'train_size': len(X_train),
        'test_size': len(X_test),
        'total_sessions': int(n_sessions),
        'train_sessions': int(train_sessions),
        'test_sessions': int(test_sessions),
        'features': feature_names,
        'best_model': best_name,
        'split_method': 'GroupShuffleSplit (by session_id)',
        'cv_method': f'GroupKFold ({n_folds}-fold by session_id)',
        'results': results,
        'classification_report_rf': classification_report(y_test, y_pred_rf, output_dict=True),
        'classification_report_gb': classification_report(y_test, y_pred_gb, output_dict=True),
    }

    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to: {report_path}")

    return best_model, scaler, feature_names


def main():
    parser = argparse.ArgumentParser(description="Train ErgoBoost posture classifier")
    parser.add_argument("--db", type=str, default="data/ergoboost.db")
    parser.add_argument("--output", type=str, default="ml/models")
    args = parser.parse_args()

    print("=" * 60)
    print("  ErgoBoost ML Training Pipeline")
    print("=" * 60)
    print(f"Database: {args.db}")
    print(f"Output:   {args.output}\n")

    # Load data
    df = load_data(args.db)
    if len(df) < 100:
        print("Not enough data to train! Need at least 100 samples.")
        return

    # Features + groups
    X, y, feature_names, groups = engineer_features(df)

    # Train
    model, scaler, features = train_and_evaluate(
        X, y, feature_names, groups, Path(args.output)
    )

    print("\n" + "=" * 60)
    print("  Training Complete!")
    print("=" * 60)
    print(f"\nTo use the model in the app:")
    print(f"  from ml.predictor import PosturePredictor")
    print(f"  predictor = PosturePredictor()")
    print(f"  result = predictor.predict(forward_shift, lateral_tilt)")


if __name__ == "__main__":
    main()
