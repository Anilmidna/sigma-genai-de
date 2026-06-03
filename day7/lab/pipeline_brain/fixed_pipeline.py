import os
import json
import logging
from datetime import datetime

from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import (
    col,
    lit,
    when,
    coalesce,
    sum,
    count,
    avg,
    first,
    last,
    broadcast,
    row_number,
    countDistinct
)

from pyspark.sql.types import FloatType, StringType, DateType

# -------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# BRONZE LAYER
# -------------------------------------------------------------------
def ingest_bronze(spark, input_path, output_path, run_date, run_id):

    try:
        logger.info("Starting Bronze ingestion")

        transactions_df = (
            spark.read.format("csv")
            .option("header", "true")
            .option("inferSchema", "false")
            .load(input_path)
        )

        transactions_df = (
            transactions_df
            .withColumn("ingestion_timestamp", lit(run_date))
            .withColumn("source_file", lit("transactions.csv"))
            .withColumn("pipeline_run_id", lit(run_id))
        )

        logger.info(f"Bronze input rows: {transactions_df.count()}")

        (
            transactions_df.write
            .mode("overwrite")
            .partitionBy("ingestion_timestamp")
            .parquet(output_path)
        )

        logger.info("Bronze ingestion completed")

    except Exception as e:
        logger.error(f"Bronze ingestion failed: {e}")
        raise


# -------------------------------------------------------------------
# SILVER LAYER
# -------------------------------------------------------------------
def transform_silver(
    spark,
    bronze_path,
    merchants_path,
    output_path,
    run_date
):

    try:
        logger.info("Starting Silver transformation")

        transactions_df = (
            spark.read.parquet(bronze_path)
            .where(col("ingestion_timestamp") == run_date)
        )

        logger.info(f"Silver input rows: {transactions_df.count()}")

        transactions_df = (
            transactions_df
            .withColumn("amount", col("amount").cast(FloatType()))
            .withColumn("transaction_date", col("transaction_date").cast(DateType()))
            .withColumn("transaction_id", col("transaction_id").cast(StringType()))
            .withColumn("merchant_id", col("merchant_id").cast(StringType()))
        )

        # NULL + negative checks
        cleaned_df = transactions_df.filter(
            (col("transaction_id").isNotNull()) &
            (col("amount") >= 0)
        )

        logger.info(f"After filter rows: {cleaned_df.count()}")

        # Deduplication
        window_spec = Window.partitionBy("transaction_id") \
                            .orderBy(col("ingestion_timestamp").desc())

        deduped_df = (
            cleaned_df
            .withColumn("rn", row_number().over(window_spec))
            .filter(col("rn") == 1)
            .drop("rn")
        )

        logger.info(f"After dedup rows: {deduped_df.count()}")

        # Merchants
        merchants_df = (
            spark.read.format("csv")
            .option("header", "true")
            .load(merchants_path)
        ).cache()

        enriched_df = (
            deduped_df.join(
                broadcast(merchants_df),
                "merchant_id",
                "left"
            )
        )

        # Quality flag
        enriched_df = enriched_df.withColumn(
            "quality_flag",
            when(
                col("merchant_name").isNull(),
                lit("UNMATCHED")
            ).otherwise(lit("CLEAN"))
        )

        (
            enriched_df.write
            .mode("overwrite")
            .partitionBy("transaction_date")
            .parquet(output_path)
        )

        logger.info(f"Silver output rows: {enriched_df.count()}")

    except Exception as e:
        logger.error(f"Silver transformation failed: {e}")
        raise


# -------------------------------------------------------------------
# GOLD LAYER
# -------------------------------------------------------------------
def build_daily_summary(spark, silver_path, output_path, run_date):

    try:
        logger.info("Starting daily summary")

        df = (
            spark.read.parquet(silver_path)
            .where(col("transaction_date") == run_date)
        )

        daily_summary = (
            df.groupBy("transaction_date")
            .agg(
                sum(
                    when(col("status") == "COMPLETED", col("amount"))
                    .otherwise(0)
                ).alias("total_revenue"),

                count("*").alias("total_txns"),

                countDistinct("customer_id").alias("unique_customers"),

                countDistinct("merchant_id").alias("unique_merchants"),

                (
                    count(
                        when(col("status") == "FAILED", 1)
                    ) / count("*") * 100
                ).alias("failure_rate_pct")
            )
        )

        (
            daily_summary.write
            .mode("overwrite")
            .partitionBy("transaction_date")
            .parquet(output_path)
        )

        logger.info(f"Daily summary rows: {daily_summary.count()}")

    except Exception as e:
        logger.error(f"Daily summary failed: {e}")
        raise


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
def main():

    spark = (
        SparkSession.builder
        .appName("Sigma Transaction Pipeline")
        .getOrCreate()
    )

    # ---------------------------------------------------------------
    # FIXED: no hardcoded paths
    # ---------------------------------------------------------------
    input_path = os.getenv("INPUT_PATH")
    bronze_path = os.getenv("BRONZE_PATH")
    silver_path = os.getenv("SILVER_PATH")
    gold_path = os.getenv("GOLD_PATH")
    merchants_path = os.getenv("MERCHANTS_PATH")

    run_date = datetime.today().strftime("%Y-%m-%d")
    run_id = f"run_{run_date}"

    try:

        ingest_bronze(
            spark,
            input_path,
            bronze_path,
            run_date,
            run_id
        )

        transform_silver(
            spark,
            bronze_path,
            merchants_path,
            silver_path,
            run_date
        )

        build_daily_summary(
            spark,
            silver_path,
            gold_path,
            run_date
        )

        metadata = {
            "run_date": run_date,
            "run_id": run_id,
            "status": "SUCCESS"
        }

        with open("run_metadata.json", "w") as f:
            json.dump(metadata, f)

        logger.info("Pipeline completed successfully")

    except Exception as e:

        logger.error(f"Pipeline failed: {e}")

        metadata = {
            "run_date": run_date,
            "run_id": run_id,
            "status": "FAILED",
            "error": str(e)
        }

        with open("run_metadata.json", "w") as f:
            json.dump(metadata, f)

        raise


if __name__ == "__main__":
    main()