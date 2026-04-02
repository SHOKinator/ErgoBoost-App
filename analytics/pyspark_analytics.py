# analytics/pyspark_analytics.py
"""
PySpark-based analytics engine for ErgoBoost.
For batch processing and advanced analytics (Big Data diploma requirement).
Requires: pyspark, sqlite-jdbc driver.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, avg, count, sum as spark_sum, max as spark_max,
    hour, dayofweek, date_format, lag, when, lit
)
from pyspark.sql.window import Window
from pyspark.sql.types import TimestampType
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict
from utils.logger import setup_logger

logger = setup_logger(__name__)


class PySparkAnalytics:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.spark = self._init_spark()
        logger.info("PySpark Analytics initialized")

    def _init_spark(self) -> SparkSession:
        spark = SparkSession.builder \
            .appName("ErgoBoost Analytics") \
            .master("local[*]") \
            .config("spark.driver.memory", "2g") \
            .config("spark.sql.warehouse.dir", "data/spark-warehouse") \
            .config("spark.jars",
                    "libs/sqlite-jdbc-3.46.0.0.jar") \
            .getOrCreate()
        spark.sparkContext.setLogLevel("WARN")
        return spark

    def _jdbc_url(self):
        return f"jdbc:sqlite:{self.db_path}"

    def _load_table(self, table):
        return self.spark.read \
            .format("jdbc") \
            .option("url", self._jdbc_url()) \
            .option("dbtable", table) \
            .option("driver", "org.sqlite.JDBC") \
            .load()

    def load_sessions(self):
        df = self._load_table("sessions")
        df = df.withColumn("start_time", col("start_time").cast(TimestampType()))
        df = df.withColumn("end_time", col("end_time").cast(TimestampType()))
        return df

    def load_posture_events(self):
        df = self._load_table("posture_events")
        return df.withColumn("timestamp", col("timestamp").cast(TimestampType()))

    def load_eye_events(self):
        df = self._load_table("eye_events")
        return df.withColumn("timestamp", col("timestamp").cast(TimestampType()))

    def load_distance_events(self):
        df = self._load_table("distance_events")
        return df.withColumn("timestamp", col("timestamp").cast(TimestampType()))

    def calculate_posture_trends(self, days=30) -> pd.DataFrame:
        sessions_df = self.load_sessions()
        posture_df = self.load_posture_events()

        cutoff = datetime.now() - timedelta(days=days)
        sessions_df = sessions_df.filter(col("start_time") >= lit(cutoff))

        joined = posture_df.join(sessions_df,
            posture_df.session_id == sessions_df.id, "inner")

        trends = joined.withColumn("date", date_format("timestamp", "yyyy-MM-dd")) \
            .groupBy("date") \
            .agg(
                count("*").alias("total_events"),
                avg("severity").alias("avg_severity"),
                (spark_sum(when(col("posture_status") == "OK", 1).otherwise(0)) /
                 count("*") * 100).alias("good_posture_percent"),
            ) \
            .orderBy("date")
        return trends.toPandas()

    def analyze_daily_patterns(self) -> pd.DataFrame:
        posture_df = self.load_posture_events()
        analysis = posture_df \
            .withColumn("hour", hour("timestamp")) \
            .withColumn("day_of_week", dayofweek("timestamp")) \
            .groupBy("hour", "day_of_week") \
            .agg(
                count("*").alias("total_events"),
                avg("severity").alias("avg_severity"),
            )
        return analysis.toPandas()

    def analyze_blink_patterns(self) -> pd.DataFrame:
        eye_df = self.load_eye_events()
        window_spec = Window.partitionBy("session_id").orderBy("timestamp")

        analysis = eye_df \
            .withColumn("prev_blink", lag("blink_count").over(window_spec)) \
            .withColumn("blink_diff", col("blink_count") - col("prev_blink")) \
            .filter(col("blink_diff").isNotNull()) \
            .groupBy("session_id") \
            .agg(
                avg("blink_diff").alias("avg_blink_rate_per_interval"),
                avg("ear").alias("avg_ear"),
                count("*").alias("measurement_count"),
            )
        return analysis.toPandas()

    def export_to_csv(self, output_dir: Path = Path("exports")):
        output_dir.mkdir(parents=True, exist_ok=True)
        self.calculate_posture_trends().to_csv(output_dir / "posture_trends.csv", index=False)
        self.analyze_daily_patterns().to_csv(output_dir / "daily_patterns.csv", index=False)
        self.analyze_blink_patterns().to_csv(output_dir / "blink_patterns.csv", index=False)
        logger.info(f"Analytics exported to {output_dir}")

    def close(self):
        self.spark.stop()
