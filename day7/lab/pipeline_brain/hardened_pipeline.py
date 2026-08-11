import shutil
import logging
import json
import os
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, broadcast, when, sum, count, max, avg, min, collect_set, coalesce
from pyspark.sql.types import FloatType, StringType, DateType

logging.basicConfig(level=logging.INFO)

def ingest_bronze(spark, input_path, output_path, run_date, run_id):
    try:
        logging.info("Starting ingest_bronze stage")
        transactions_df = (spark.read.option("header", "true")
                          .option("inferSchema", "false")
                          .csv(input_path + "/transactions.csv"))

        merchants_df = (spark.read.option("header", "true")
                       .option("inferSchema", "false")
                        .csv(input_path + "/merchants.csv"))

        transactions_df = (transactions_df.withColumn("ingestion_timestamp", lit(run_date))
                           .withColumn("source_file", lit("transactions.csv"))
                          .withColumn("pipeline_run_id", lit(run_id)))

        partition_path = f"{output_path}/bronze/transactions/ingestion_timestamp={run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        transactions_df.write.mode("overwrite").partitionBy("ingestion_timestamp").parquet(output_path + "/bronze/transactions")

        partition_path = f"{output_path}/bronze/merchants/ingestion_timestamp={run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        merchants_df.write.mode("overwrite").partitionBy("ingestion_timestamp").parquet(output_path + "/bronze/merchants")

        logging.info(f"[Stage: ingest_bronze] Ingested {transactions_df.count():,} transaction rows and {merchants_df.count():,} merchant rows")

    except Exception as e:
        logging.error(f"Error in ingest_bronze stage: {e}")
        raise

def transform_silver(spark, bronze_path, merchants_path, output_path, run_date):
    try:
        logging.info("Starting transform_silver stage")
        transactions_df = (spark.read.parquet(bronze_path + "/bronze/transactions")
                          .where(col("ingestion_timestamp") == run_date))

        merchants_df = (spark.read.parquet(merchants_path + "/bronze/merchants")
                        .where(col("ingestion_timestamp") == run_date)
                        .cache())

        transactions_df = (transactions_df.withColumn("amount", col("amount").cast(FloatType()))
                          .withColumn("transaction_date", col("transaction_date").cast(DateType()))
                          .withColumn("transaction_id", col("transaction_id").cast(StringType()))
                          .withColumn("merchant_id", col("merchant_id").cast(StringType())))

        input_count = transactions_df.count()
        logging.info(f"[Stage: transform_silver] Input count: {input_count:,} rows")

        transactions_df = transactions_df.filter((col("transaction_id").isNotNull()) & (col("amount") >= 0))
        after_filter_count = transactions_df.count()
        logging.info(f"[Stage: transform_silver] After filter count: {after_filter_count:,} rows")

        transactions_dedup_df = (transactions_df.groupBy("transaction_id")
                                 .agg({"amount": "max", "ingestion_timestamp": "max"})
                                 .withColumnRenamed("max(amount)", "amount")
                                .withColumnRenamed("max(ingestion_timestamp)", "ingestion_timestamp"))

        after_dedup_count = transactions_dedup_df.count()
        logging.info(f"[Stage: transform_silver] After dedup count: {after_dedup_count:,} rows")

        transactions_enriched_df = (transactions_dedup_df.join(broadcast(merchants_df), "merchant_id", "left_outer")
                                    .withColumn("quality_flag", when(col("merchant_id").isNull(), "UNMATCHED").otherwise("CLEAN")))

        output_count = transactions_enriched_df.count()
        logging.info(f"[Stage: transform_silver] Output count: {output_count:,} rows")

        partition_path = f"{output_path}/silver/transactions/transaction_date={run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        transactions_enriched_df.write.mode("overwrite").partitionBy("transaction_date").parquet(output_path + "/silver/transactions")

    except Exception as e:
        logging.error(f"Error in transform_silver stage: {e}")
        raise

def main(spark, input_path, output_path, run_date, run_id):
    try:
        logging.info("Starting main pipeline")
        started_at = datetime.now().isoformat()

        ingest_bronze(spark, input_path, output_path, run_date, run_id)
        transform_silver(spark, output_path, output_path, output_path, run_date)

        completed_at = datetime.now().isoformat()
        run_metadata = {
            "pipeline_name": "Sigma DataTech Transaction Analytics Pipeline",
            "run_date": run_date,
            "run_id": run_id,
            "run_status": "SUCCESS",
            "started_at": started_at,
            "completed_at": completed_at,
            "error_message": None
        }

        with open(os.path.join(output_path, f"run_metadata_{run_date}.json"), "w") as f:
            json.dump(run_metadata, f)

    except Exception as e:
        completed_at = datetime.now().isoformat()
        run_metadata = {
            "pipeline_name": "Sigma DataTech Transaction Analytics Pipeline",
            "run_date": run_date,
            "run_id": run_id,
            "run_status": "FAILED",
            "started_at": started_at,
            "completed_at": completed_at,
            "error_message": str(e)
        }

        with open(os.path.join(output_path, f"run_metadata_{run_date}.json"), "w") as f:
            json.dump(run_metadata, f)

        raise

def run_gold(spark, silver_path, gold_output_dir, run_date):
    try:
        logging.info("Starting run_gold stage")
        started_at = datetime.now().isoformat()

        run_metadata = {
            "run_date": run_date,
            "silver_path": silver_path,
            "gold_output_dir": gold_output_dir,
            "tables": []
        }

        build_merchant_performance(spark, silver_path, f"{gold_output_dir}/merchant_performance", run_date)
        build_customer_ltv(spark, silver_path, f"{gold_output_dir}/customer_ltv")
        build_daily_summary(spark, silver_path, f"{gold_output_dir}/daily_summary", run_date)

        completed_at = datetime.now().isoformat()
        run_metadata["completed_at"] = completed_at
        run_metadata["run_status"] = "SUCCESS"
        run_metadata["error_message"] = None

        with open(f"{gold_output_dir}/run_metadata.json", "w") as f:
            json.dump(run_metadata, f)

    except Exception as e:
        completed_at = datetime.now().isoformat()
        run_metadata["completed_at"] = completed_at
        run_metadata["run_status"] = "FAILED"
        run_metadata["error_message"] = str(e)

        with open(f"{gold_output_dir}/run_metadata.json", "w") as f:
            json.dump(run_metadata, f)

        raise

def build_merchant_performance(spark, silver_path, output_path, run_date):
    try:
        logging.info("Starting build_merchant_performance stage")
        silver_df = spark.read.parquet(silver_path).where(col("date") == run_date)  # Partition pruning

        completed_txns = silver_df.where(col("status") == "COMPLETED")
        merchant_performance_df = completed_txns.groupBy("merchant_id", "merchant_name", "category", "city", "date") \
            .agg(
                sum("amount").alias("total_revenue"),
                count("*").alias("txn_count")
            )

        all_txns = silver_df.groupBy("merchant_id").agg(
            count("*").alias("total_txns"),
            count(when(col("status") == "FAILED", 1)).alias("failed_txns")
        )

        failure_rate_df = all_txns.withColumn("failure_rate_pct", (col("failed_txns") / col("total_txns") * 100).cast("float"))

        final_df = merchant_performance_df.join(failure_rate_df, on=["merchant_id"], how="left") \
           .select("merchant_id", "merchant_name", "category", "city", "date", "total_revenue", "txn_count", "failure_rate_pct")

        partition_path = f"{output_path}/date={run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        final_df.write.mode("overwrite").partitionBy("date").parquet(output_path)

    except Exception as e:
        logging.error(f"Error in build_merchant_performance stage: {e}")
        raise

def build_customer_ltv(spark, silver_path, output_path):
    try:
        logging.info("Starting build_customer_ltv stage")
        silver_df = spark.read.parquet(silver_path)

        completed_txns = silver_df.where(col("status") == "COMPLETED")
        customer_ltv_df = completed_txns.groupBy("customer_id") \
           .agg(
                sum("amount").alias("total_spent"),
                count("*").alias("total_txns"),
                avg("amount").alias("avg_txn_value"),
                min("transaction_date").alias("first_txn_date"),
                max("transaction_date").alias("last_txn_date")
            )

        payment_method_df = completed_txns.groupBy("customer_id", "payment_method") \
           .agg(count("*").alias("payment_count")) \
           .groupBy("customer_id") \
            .agg(max("payment_count").alias("max_count"), collect_set("payment_method").alias("payment_methods")) \
           .withColumn("preferred_payment_method", coalesce(max("payment_methods")[0], lit(None)))

        final_df = customer_ltv_df.join(payment_method_df, on=["customer_id"], how="left") \
           .select("customer_id", "total_spent", "total_txns", "avg_txn_value", "first_txn_date", "last_txn_date", "preferred_payment_method")

        partition_path = output_path
        shutil.rmtree(partition_path, ignore_errors=True)
        final_df.write.mode("overwrite").parquet(output_path)

    except Exception as e:
        logging.error(f"Error in build_customer_ltv stage: {e}")
        raise

def build_daily_summary(spark, silver_path, output_path, run_date):
    try:
        logging.info("Starting build_daily_summary stage")
        silver_df = spark.read.parquet(silver_path).where(col("date") == run_date)  # Partition pruning

        daily_summary_df = silver_df.groupBy("date") \
           .agg(
                sum(when(col("status") == "COMPLETED", col("amount")).otherwise(lit(0))).alias("total_revenue"),
                count("*").alias("total_txns"),
                count(col("customer_id").distinct()).alias("unique_customers"),
                count(col("merchant_id").distinct()).alias("unique_merchants")
            )

        all_txns = silver_df.groupBy("date").agg(
            count("*").alias("total_txns"),
            count(when(col("status") == "FAILED", 1)).alias("failed_txns")
        )

        failure_rate_df = all_txns.withColumn("failure_rate_pct", (col("failed_txns") / col("total_txns") * 100).cast("float"))

        final_df = daily_summary_df.join(failure_rate_df, on=["date"], how="left") \
           .select("date", "total_revenue", "total_txns", "unique_customers", "unique_merchants", "failure_rate_pct")

        partition_path = f"{output_path}/date={run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        final_df.write.mode("overwrite").partitionBy("date").parquet(output_path)

    except Exception as e:
        logging.error(f"Error in build_daily_summary stage: {e}")
        raise

if __name__ == "__main__":
    spark = (SparkSession.builder
            .appName("Sigma DataTech Transaction Analytics Pipeline")
             .getOrCreate())

    input_path = "s3://your-bucket/bronze"
    output_path = "s3://your-bucket/silver"
    run_date = "2026-05-27"
    run_id = "run_id_12345"

    main(spark, input_path, output_path, run_date, run_id)
