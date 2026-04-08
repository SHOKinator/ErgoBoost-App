# ml/train_posture_model.py
"""
PySpark MLlib Pipeline for ErgoBoost.
Trains a posture quality classifier on collected session data.

Pipeline:
1. ETL: Load from SQLite → Spark DataFrame
2. Feature Engineering: combine posture + eye + distance features
3. Train: Random Forest + Gradient Boosted Trees
4. Evaluate: accuracy, precision, recall, F1, confusion matrix
5. Save: model + comparison report (rule-based vs ML)

Usage:
    python -m ml.train_posture_model
    python -m ml.train_posture_model --db data/ergoboost.db --output ml/models
"""

import sys
import argparse
import sqlite3
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, avg, count, when, lit, lag, abs as spark_abs,
    hour, minute, dayofweek, unix_timestamp
)
from pyspark.sql.window import Window
from pyspark.sql.types import (
    StructType, StructField, FloatType, IntegerType, StringType
)
from pyspark.ml.feature import (
    VectorAssembler, StringIndexer, StandardScaler
)
from pyspark.ml.classification import (
    RandomForestClassifier, GBTClassifier, LogisticRegression
)
from pyspark.ml.evaluation import (
    MulticlassClassificationEvaluator, BinaryClassificationEvaluator
)
from pyspark.ml import Pipeline
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder


def create_spark():
    """Create Spark session"""
    spark = SparkSession.builder \
        .appName("ErgoBoost ML Training") \
        .master("local[*]") \
        .config("spark.driver.memory", "4g") \
        .config("spark.sql.shuffle.partitions", "8") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def load_data_from_sqlite(db_path: str):
    """Load data from SQLite into pandas, return dict of DataFrames"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    posture_df = __import__('pandas').read_sql_query(
        "SELECT * FROM posture_events WHERE forward_shift IS NOT NULL AND lateral_tilt IS NOT NULL",
        conn
    )
    eye_df = __import__('pandas').read_sql_query(
        "SELECT * FROM eye_events WHERE ear IS NOT NULL", conn
    )
    distance_df = __import__('pandas').read_sql_query(
        "SELECT * FROM distance_events WHERE distance_ratio IS NOT NULL", conn
    )
    sessions_df = __import__('pandas').read_sql_query(
        "SELECT * FROM sessions WHERE end_time IS NOT NULL", conn
    )
    conn.close()

    return {
        'posture': posture_df,
        'eye': eye_df,
        'distance': distance_df,
        'sessions': sessions_df,
    }


def build_feature_dataset(spark, data):
    """
    Build feature dataset by joining posture + eye + distance events
    on session_id and closest timestamp.

    Features:
    - forward_shift (posture)
    - lateral_tilt (posture)
    - ear (eye aspect ratio)
    - blink_rate_per_min
    - distance_ratio
    - hour_of_day (temporal)
    - day_of_week (temporal)
    - time_in_session (seconds since session start)

    Label: posture_status (OK=0, BAD=1)
    """
    import pandas as pd

    posture_pdf = data['posture']
    eye_pdf = data['eye']
    distance_pdf = data['distance']
    sessions_pdf = data['sessions']

    print(f"  Raw data: {len(posture_pdf)} posture, {len(eye_pdf)} eye, {len(distance_pdf)} distance events")

    # Merge posture with eye events (same session_id, closest timestamp)
    # For simplicity, merge on session_id and row number within session
    posture_pdf['_row'] = posture_pdf.groupby('session_id').cumcount()
    eye_pdf['_row'] = eye_pdf.groupby('session_id').cumcount()
    distance_pdf['_row'] = distance_pdf.groupby('session_id').cumcount()

    # Inner join on session_id + _row
    merged = posture_pdf.merge(
        eye_pdf[['session_id', '_row', 'ear', 'blink_rate_per_min', 'fatigue_level']],
        on=['session_id', '_row'],
        how='inner'
    )
    merged = merged.merge(
        distance_pdf[['session_id', '_row', 'distance_ratio']],
        on=['session_id', '_row'],
        how='inner'
    )

    # Add session start time for temporal features
    merged = merged.merge(
        sessions_pdf[['id', 'start_time']].rename(columns={'id': 'session_id'}),
        on='session_id',
        how='left'
    )

    # Parse timestamps
    merged['ts'] = pd.to_datetime(merged['timestamp'])
    merged['session_start'] = pd.to_datetime(merged['start_time'])
    merged['hour_of_day'] = merged['ts'].dt.hour
    merged['day_of_week'] = merged['ts'].dt.dayofweek
    merged['time_in_session'] = (merged['ts'] - merged['session_start']).dt.total_seconds()

    # Select features + label
    feature_cols = [
        'forward_shift', 'lateral_tilt', 'ear', 'blink_rate_per_min',
        'distance_ratio', 'hour_of_day', 'day_of_week', 'time_in_session'
    ]

    result = merged[feature_cols + ['posture_status', 'severity', 'session_id']].dropna()
    result['label'] = (result['posture_status'] == 'BAD').astype(int)

    print(f"  Feature dataset: {len(result)} rows")
    print(f"  Label distribution: OK={len(result[result.label==0])}, BAD={len(result[result.label==1])}")

    # Convert to Spark DataFrame
    spark_df = spark.createDataFrame(result)
    return spark_df


def train_and_evaluate(spark, df, output_dir: Path):
    """Train multiple models and evaluate them"""
    output_dir.mkdir(parents=True, exist_ok=True)

    feature_cols = [
        'forward_shift', 'lateral_tilt', 'ear', 'blink_rate_per_min',
        'distance_ratio', 'hour_of_day', 'day_of_week', 'time_in_session'
    ]

    # Assemble features
    assembler = VectorAssembler(inputCols=feature_cols, outputCol="raw_features")
    scaler = StandardScaler(inputCol="raw_features", outputCol="features",
                            withStd=True, withMean=True)

    # Split data
    train_df, test_df = df.randomSplit([0.8, 0.2], seed=42)
    print(f"\n  Train: {train_df.count()} rows, Test: {test_df.count()} rows")

    results = {}

    # === Model 1: Random Forest ===
    print("\n  Training Random Forest...")
    rf = RandomForestClassifier(
        labelCol="label", featuresCol="features",
        numTrees=100, maxDepth=10, seed=42
    )
    rf_pipeline = Pipeline(stages=[assembler, scaler, rf])
    rf_model = rf_pipeline.fit(train_df)
    rf_predictions = rf_model.transform(test_df)

    rf_metrics = evaluate_model(rf_predictions, "Random Forest")
    results['random_forest'] = rf_metrics

    # Save RF model
    rf_model_path = str(output_dir / "random_forest_model")
    rf_model.write().overwrite().save(rf_model_path)
    print(f"  Saved to {rf_model_path}")

    # Feature importance
    rf_actual = rf_model.stages[-1]  # RandomForestClassificationModel
    importances = rf_actual.featureImportances.toArray()
    fi = list(zip(feature_cols, importances))
    fi.sort(key=lambda x: x[1], reverse=True)
    print("  Feature Importance:")
    for name, imp in fi:
        print(f"    {name}: {imp:.4f}")
    results['feature_importance'] = {name: float(imp) for name, imp in fi}

    # === Model 2: Gradient Boosted Trees ===
    print("\n  Training Gradient Boosted Trees...")
    gbt = GBTClassifier(
        labelCol="label", featuresCol="features",
        maxIter=50, maxDepth=8, seed=42
    )
    gbt_pipeline = Pipeline(stages=[assembler, scaler, gbt])
    gbt_model = gbt_pipeline.fit(train_df)
    gbt_predictions = gbt_model.transform(test_df)

    gbt_metrics = evaluate_model(gbt_predictions, "GBT")
    results['gbt'] = gbt_metrics

    gbt_model_path = str(output_dir / "gbt_model")
    gbt_model.write().overwrite().save(gbt_model_path)
    print(f"  Saved to {gbt_model_path}")

    # === Model 3: Logistic Regression (baseline) ===
    print("\n  Training Logistic Regression (baseline)...")
    lr = LogisticRegression(
        labelCol="label", featuresCol="features",
        maxIter=100
    )
    lr_pipeline = Pipeline(stages=[assembler, scaler, lr])
    lr_model = lr_pipeline.fit(train_df)
    lr_predictions = lr_model.transform(test_df)

    lr_metrics = evaluate_model(lr_predictions, "Logistic Regression")
    results['logistic_regression'] = lr_metrics

    # === Rule-Based Baseline ===
    print("\n  Evaluating Rule-Based baseline...")
    # Rule-based: severity > 1.0 => BAD
    rule_predictions = test_df.withColumn(
        "rule_prediction",
        when(col("severity") > 1.0, 1.0).otherwise(0.0)
    )
    rule_correct = rule_predictions.filter(
        col("rule_prediction") == col("label")
    ).count()
    rule_total = rule_predictions.count()
    rule_accuracy = rule_correct / rule_total if rule_total > 0 else 0

    # Rule-based precision/recall for BAD class
    rule_tp = rule_predictions.filter(
        (col("rule_prediction") == 1) & (col("label") == 1)
    ).count()
    rule_fp = rule_predictions.filter(
        (col("rule_prediction") == 1) & (col("label") == 0)
    ).count()
    rule_fn = rule_predictions.filter(
        (col("rule_prediction") == 0) & (col("label") == 1)
    ).count()

    rule_precision = rule_tp / (rule_tp + rule_fp) if (rule_tp + rule_fp) > 0 else 0
    rule_recall = rule_tp / (rule_tp + rule_fn) if (rule_tp + rule_fn) > 0 else 0
    rule_f1 = 2 * rule_precision * rule_recall / (rule_precision + rule_recall) \
        if (rule_precision + rule_recall) > 0 else 0

    results['rule_based'] = {
        'accuracy': round(rule_accuracy, 4),
        'precision': round(rule_precision, 4),
        'recall': round(rule_recall, 4),
        'f1': round(rule_f1, 4),
    }
    print(f"  Rule-Based: accuracy={rule_accuracy:.4f}, precision={rule_precision:.4f}, "
          f"recall={rule_recall:.4f}, F1={rule_f1:.4f}")

    # === Cross-validation for best model (RF) ===
    print("\n  Running cross-validation on Random Forest...")
    paramGrid = ParamGridBuilder() \
        .addGrid(rf.numTrees, [50, 100, 200]) \
        .addGrid(rf.maxDepth, [5, 10, 15]) \
        .build()

    evaluator = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="f1"
    )

    cv = CrossValidator(
        estimator=rf_pipeline,
        estimatorParamMaps=paramGrid,
        evaluator=evaluator,
        numFolds=3,
        seed=42
    )
    cv_model = cv.fit(train_df)
    cv_predictions = cv_model.transform(test_df)
    cv_f1 = evaluator.evaluate(cv_predictions)
    print(f"  Best CV F1: {cv_f1:.4f}")

    # Save best model
    best_model_path = str(output_dir / "best_model")
    cv_model.bestModel.write().overwrite().save(best_model_path)
    print(f"  Best model saved to {best_model_path}")

    results['cross_validation'] = {
        'best_f1': round(cv_f1, 4),
        'num_folds': 3,
        'param_grid_size': len(paramGrid),
    }

    # === Summary Report ===
    print("\n" + "=" * 60)
    print("  MODEL COMPARISON SUMMARY")
    print("=" * 60)
    print(f"  {'Model':<25} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")

    for name, key in [
        ("Rule-Based", "rule_based"),
        ("Logistic Regression", "logistic_regression"),
        ("Random Forest", "random_forest"),
        ("Gradient Boosted Trees", "gbt"),
    ]:
        m = results[key]
        print(f"  {name:<25} {m['accuracy']:>10.4f} {m['precision']:>10.4f} "
              f"{m['recall']:>10.4f} {m['f1']:>10.4f}")

    print(f"\n  Best CV (Random Forest): F1 = {cv_f1:.4f}")
    print("=" * 60)

    # Save report
    report = {
        'trained_at': datetime.now().isoformat(),
        'dataset_size': df.count(),
        'train_size': train_df.count(),
        'test_size': test_df.count(),
        'features': feature_cols,
        'models': results,
    }
    report_path = output_dir / "training_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved to {report_path}")

    return results


def evaluate_model(predictions, model_name):
    """Evaluate a model's predictions"""
    evaluator_acc = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="accuracy"
    )
    evaluator_f1 = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="f1"
    )
    evaluator_precision = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="weightedPrecision"
    )
    evaluator_recall = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="weightedRecall"
    )

    accuracy = evaluator_acc.evaluate(predictions)
    f1 = evaluator_f1.evaluate(predictions)
    precision = evaluator_precision.evaluate(predictions)
    recall = evaluator_recall.evaluate(predictions)

    print(f"  {model_name}: accuracy={accuracy:.4f}, precision={precision:.4f}, "
          f"recall={recall:.4f}, F1={f1:.4f}")

    # Confusion matrix
    tp = predictions.filter((col("prediction") == 1) & (col("label") == 1)).count()
    fp = predictions.filter((col("prediction") == 1) & (col("label") == 0)).count()
    fn = predictions.filter((col("prediction") == 0) & (col("label") == 1)).count()
    tn = predictions.filter((col("prediction") == 0) & (col("label") == 0)).count()

    print(f"    Confusion Matrix: TP={tp}, FP={fp}, FN={fn}, TN={tn}")

    return {
        'accuracy': round(accuracy, 4),
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1': round(f1, 4),
        'confusion_matrix': {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn},
    }


def main():
    parser = argparse.ArgumentParser(description="Train ErgoBoost posture ML model")
    parser.add_argument("--db", type=str, default="data/ergoboost.db")
    parser.add_argument("--output", type=str, default="ml/models")
    args = parser.parse_args()

    print("=" * 60)
    print("  ErgoBoost ML Training Pipeline (PySpark MLlib)")
    print("=" * 60)
    print(f"  DB: {args.db}")
    print(f"  Output: {args.output}")

    # Step 1: Create Spark
    print("\n[1/4] Starting Spark...")
    spark = create_spark()

    # Step 2: Load & ETL
    print("\n[2/4] Loading data from SQLite...")
    data = load_data_from_sqlite(args.db)

    # Step 3: Feature Engineering
    print("\n[3/4] Building feature dataset...")
    df = build_feature_dataset(spark, data)

    if df.count() < 100:
        print("ERROR: Not enough data to train. Need at least 100 rows.")
        print("Run: python -m tools.generate_synthetic_data --users 5 --days 90")
        spark.stop()
        return

    # Step 4: Train & Evaluate
    print("\n[4/4] Training models...")
    results = train_and_evaluate(spark, df, Path(args.output))

    print("\nDone! Models saved to:", args.output)
    spark.stop()


if __name__ == "__main__":
    main()
