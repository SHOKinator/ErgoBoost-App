# ml/train_pyspark.py
"""
PySpark MLlib Training Pipeline for ErgoBoost.
Trains posture classifier using distributed computing.

For Big Data diploma: demonstrates PySpark ML pipeline on large dataset.

Requirements:
    pip install pyspark
    Download sqlite-jdbc jar to libs/ folder

Usage:
    python -m ml.train_pyspark
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql.functions import col, abs as spark_abs, when
        from pyspark.sql.types import DoubleType
        from pyspark.ml.feature import VectorAssembler, StandardScaler
        from pyspark.ml.classification import RandomForestClassifier, GBTClassifier
        from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator
        from pyspark.ml import Pipeline
    except ImportError:
        print("PySpark not installed. Install with: pip install pyspark")
        print("Also need sqlite-jdbc jar in libs/ folder.")
        return

    print("=" * 60)
    print("  ErgoBoost PySpark MLlib Training Pipeline")
    print("=" * 60)

    db_path = "data/ergoboost.db"
    jdbc_jar = "libs/sqlite-jdbc-3.46.0.0.jar"

    if not Path(jdbc_jar).exists():
        print(f"\nWARNING: JDBC jar not found at {jdbc_jar}")
        print("Download from: https://github.com/xerial/sqlite-jdbc/releases")
        print("Place it in libs/ folder")
        return

    # Initialize Spark
    print("\nInitializing Spark...")
    spark = SparkSession.builder \
        .appName("ErgoBoost ML Training") \
        .master("local[*]") \
        .config("spark.driver.memory", "4g") \
        .config("spark.jars", jdbc_jar) \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    jdbc_url = f"jdbc:sqlite:{db_path}"

    # Load data
    print("Loading data from SQLite via JDBC...")

    posture_df = spark.read.format("jdbc") \
        .option("url", jdbc_url) \
        .option("dbtable", "posture_events") \
        .option("driver", "org.sqlite.JDBC") \
        .load()

    eye_df = spark.read.format("jdbc") \
        .option("url", jdbc_url) \
        .option("dbtable", "eye_events") \
        .option("driver", "org.sqlite.JDBC") \
        .load()

    distance_df = spark.read.format("jdbc") \
        .option("url", jdbc_url) \
        .option("dbtable", "distance_events") \
        .option("driver", "org.sqlite.JDBC") \
        .load()

    print(f"  Posture events: {posture_df.count():,}")
    print(f"  Eye events: {eye_df.count():,}")
    print(f"  Distance events: {distance_df.count():,}")

    # Merge datasets
    print("\nMerging datasets...")

    # Join posture with eye events on session_id + timestamp
    merged = posture_df.join(
        eye_df.select("session_id", "timestamp", "ear", "blink_rate_per_min"),
        on=["session_id", "timestamp"],
        how="inner"
    )
    merged = merged.join(
        distance_df.select("session_id", "timestamp", "distance_ratio"),
        on=["session_id", "timestamp"],
        how="inner"
    )

    # Filter nulls
    merged = merged.filter(
        col("forward_shift").isNotNull() &
        col("lateral_tilt").isNotNull() &
        col("ear").isNotNull() &
        col("distance_ratio").isNotNull()
    )

    # Create label: OK=0, BAD=1
    merged = merged.withColumn("label",
        when(col("posture_status") == "BAD", 1.0).otherwise(0.0).cast(DoubleType())
    )

    # Feature engineering
    merged = merged.withColumn("shift_abs", spark_abs(col("forward_shift")))
    merged = merged.withColumn("tilt_abs", spark_abs(col("lateral_tilt")))
    merged = merged.withColumn("shift_x_tilt",
        spark_abs(col("forward_shift")) * spark_abs(col("lateral_tilt")))

    total = merged.count()
    bad_count = merged.filter(col("label") == 1.0).count()
    print(f"  Merged dataset: {total:,} samples")
    print(f"  OK: {total - bad_count:,}, BAD: {bad_count:,}")

    if total < 100:
        print("Not enough data!")
        spark.stop()
        return

    # ML Pipeline
    feature_cols = [
        "forward_shift", "lateral_tilt", "ear",
        "blink_rate_per_min", "distance_ratio",
        "shift_abs", "tilt_abs", "shift_x_tilt"
    ]

    assembler = VectorAssembler(inputCols=feature_cols, outputCol="raw_features")
    scaler = StandardScaler(inputCol="raw_features", outputCol="features",
                           withStd=True, withMean=True)

    # Train/test split
    train_df, test_df = merged.randomSplit([0.8, 0.2], seed=42)
    print(f"\nTrain: {train_df.count():,}, Test: {test_df.count():,}")

    # ===== Random Forest =====
    print("\n--- Training Random Forest (PySpark MLlib) ---")
    rf = RandomForestClassifier(
        featuresCol="features", labelCol="label",
        numTrees=100, maxDepth=12, seed=42
    )
    rf_pipeline = Pipeline(stages=[assembler, scaler, rf])
    rf_model = rf_pipeline.fit(train_df)
    rf_predictions = rf_model.transform(test_df)

    # Evaluate
    binary_eval = BinaryClassificationEvaluator(labelCol="label")
    multi_eval = MulticlassClassificationEvaluator(labelCol="label")

    rf_auc = binary_eval.evaluate(rf_predictions, {binary_eval.metricName: "areaUnderROC"})
    rf_acc = multi_eval.evaluate(rf_predictions, {multi_eval.metricName: "accuracy"})
    rf_f1 = multi_eval.evaluate(rf_predictions, {multi_eval.metricName: "f1"})
    rf_prec = multi_eval.evaluate(rf_predictions, {multi_eval.metricName: "weightedPrecision"})
    rf_rec = multi_eval.evaluate(rf_predictions, {multi_eval.metricName: "weightedRecall"})

    print(f"  AUC-ROC:   {rf_auc:.4f}")
    print(f"  Accuracy:  {rf_acc:.4f}")
    print(f"  F1 Score:  {rf_f1:.4f}")
    print(f"  Precision: {rf_prec:.4f}")
    print(f"  Recall:    {rf_rec:.4f}")

    # Feature importance
    rf_stage = rf_model.stages[-1]
    print("\n  Feature Importance:")
    for name, imp in sorted(zip(feature_cols, rf_stage.featureImportances.toArray()),
                            key=lambda x: x[1], reverse=True):
        bar = '#' * int(imp * 50)
        print(f"    {name:25s} {imp:.4f} {bar}")

    # ===== GBT =====
    print("\n--- Training Gradient Boosted Trees (PySpark MLlib) ---")
    gbt = GBTClassifier(
        featuresCol="features", labelCol="label",
        maxIter=100, maxDepth=6, seed=42
    )
    gbt_pipeline = Pipeline(stages=[assembler, scaler, gbt])
    gbt_model = gbt_pipeline.fit(train_df)
    gbt_predictions = gbt_model.transform(test_df)

    gbt_auc = binary_eval.evaluate(gbt_predictions, {binary_eval.metricName: "areaUnderROC"})
    gbt_acc = multi_eval.evaluate(gbt_predictions, {multi_eval.metricName: "accuracy"})
    gbt_f1 = multi_eval.evaluate(gbt_predictions, {multi_eval.metricName: "f1"})

    print(f"  AUC-ROC:   {gbt_auc:.4f}")
    print(f"  Accuracy:  {gbt_acc:.4f}")
    print(f"  F1 Score:  {gbt_f1:.4f}")

    # Save PySpark model
    output_dir = Path("ml/models/spark")
    output_dir.mkdir(parents=True, exist_ok=True)

    best_name = "RandomForest" if rf_f1 >= gbt_f1 else "GBT"
    best_model = rf_model if rf_f1 >= gbt_f1 else gbt_model

    model_path = str(output_dir / "posture_classifier_spark")
    best_model.write().overwrite().save(model_path)
    print(f"\nPySpark model saved to: {model_path}")

    # Summary
    print("\n" + "=" * 60)
    print("  Results Summary")
    print("=" * 60)
    print(f"  {'Model':<25} {'Accuracy':>10} {'F1':>10} {'AUC':>10}")
    print(f"  {'-'*55}")
    print(f"  {'Random Forest':<25} {rf_acc:>10.4f} {rf_f1:>10.4f} {rf_auc:>10.4f}")
    print(f"  {'Gradient Boosted Trees':<25} {gbt_acc:>10.4f} {gbt_f1:>10.4f} {gbt_auc:>10.4f}")
    print(f"\n  Best: {best_name}")
    print(f"  Dataset: {total:,} samples from SQLite via JDBC")
    print(f"  Processing: PySpark local[*]")
    print("=" * 60)

    spark.stop()


if __name__ == "__main__":
    main()
