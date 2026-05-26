import shutil
import logging
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, broadcast, when, sum, count, max, coalesce, mode, collect_set, countDistinct
from pyspark.sql.types import StringType, FloatType, DateType
import json
import os

logging.basicConfig(level=logging.INFO)

def ingest_bronze(spark, input_path, output_path, run_date, run_id):
    try:
        logging.info("Starting ingest_bronze stage")
        transactions_df = (spark.read.option("header", "true")
                          .option("inferSchema", "false")
                           .csv(input_path))
        
        input_count = transactions_df.count()
        logging.info(f"[Stage: ingest_bronze] input_count: {input_count:,} rows")

        transactions_df = (transactions_df.withColumn("ingestion_timestamp", lit(run_date))
                           .withColumn("source_file", lit("transactions.csv"))
                          .withColumn("pipeline_run_id", lit(run_id)))

        partition_path = f"{output_path}/ingestion_timestamp={run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        transactions_df.write.mode("overwrite").partitionBy("ingestion_timestamp").parquet(output_path)
        
        output_count = spark.read.parquet(output_path).where(col("ingestion_timestamp") == run_date).count()
        logging.info(f"[Stage: ingest_bronze] output_count: {output_count:,} rows")
        
    except Exception as e:
        logging.error(f"Error in ingest_bronze: {e}")
        raise

def transform_silver(spark, bronze_path, merchants_path, output_path, run_date):
    try:
        logging.info("Starting transform_silver stage")
        transactions_df = (spark.read.parquet(bronze_path)
                           .where(col("ingestion_timestamp") == run_date))

        input_count = transactions_df.count()
        logging.info(f"[Stage: transform_silver] input_count: {input_count:,} rows")

        transactions_df = (transactions_df.withColumn("amount", col("amount").cast(FloatType()))
                          .withColumn("transaction_date", col("transaction_date").cast(DateType()))
                          .withColumn("transaction_id", col("transaction_id").cast(StringType()))
                          .withColumn("merchant_id", col("merchant_id").cast(StringType())))

        transactions_df = transactions_df.filter((col("transaction_id").isNotNull()) & (col("amount") >= 0))
        after_filter_count = transactions_df.count()
        logging.info(f"[Stage: transform_silver] after_filter_count: {after_filter_count:,} rows")

        merchants_df = (spark.read.option("header", "true").csv(merchants_path)
                        .withColumn("merchant_id", col("merchant_id").cast(StringType())))
        merchants_df = merchants_df.cache()

        transactions_df = (transactions_df.withColumn("rank",
                            (col("ingestion_timestamp").cast("long")).desc_nulls_last())
                           .filter(col("rank") == 1).drop("rank"))
        after_dedup_count = transactions_df.count()
        logging.info(f"[Stage: transform_silver] after_dedup_count: {after_dedup_count:,} rows")

        enriched_df = (transactions_df.join(broadcast(merchants_df), "merchant_id", "left")
                       .withColumn("quality_flag",
                                   when(col("merchant_id").isNull(), "UNMATCHED").otherwise("CLEAN")))

        partition_path = f"{output_path}/transaction_date={run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        enriched_df.write.mode("overwrite").partitionBy("transaction_date").parquet(output_path)

        output_count = spark.read.parquet(output_path).where(col("transaction_date") == run_date).count()
        logging.info(f"[Stage: transform_silver] output_count: {output_count:,} rows")
        
    except Exception as e:
        logging.error(f"Error in transform_silver: {e}")
        raise

def build_merchant_performance(spark, silver_path, output_path, run_date):
    try:
        logging.info("Starting build_merchant_performance stage")
        silver_df = spark.read.parquet(silver_path).filter(col("transaction_date") == run_date)  # Partition pruning
        
        merchant_performance_df = (silver_df
           .filter(col("status") == "COMPLETED")
           .groupBy("merchant_id", "merchant_name", "category", "city", "transaction_date")
           .agg(
                sum(col("amount")).alias("total_revenue"),
                count("*").alias("txn_count"),
                (count(when(col("status") == "FAILED", 1)) / count("*") * 100).alias("failure_rate_pct")
            ))
        
        partition_path = f"{output_path}/transaction_date={run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        merchant_performance_df.write.mode("overwrite").partitionBy("transaction_date").parquet(output_path)
        
        output_count = spark.read.parquet(output_path).where(col("transaction_date") == run_date).count()
        logging.info(f"[Stage: build_merchant_performance] output_count: {output_count:,} rows")
        
    except Exception as e:
        logging.error(f"Error in build_merchant_performance: {e}")
        raise

def build_customer_ltv(spark, silver_path, output_path):
    try:
        logging.info("Starting build_customer_ltv stage")
        silver_df = spark.read.parquet(silver_path).filter(col("status") == "COMPLETED")
        
        customer_ltv_df = (silver_df
           .groupBy("customer_id")
           .agg(
                sum("amount").alias("total_spent"),
                count("*").alias("total_txns"),
                avg("amount").alias("avg_txn_value"),
                min("transaction_date").alias("first_txn_date"),
                max("transaction_date").alias("last_txn_date"),
                mode("payment_method").alias("preferred_payment_method")
            ))
        
        customer_ltv_df.write.mode("overwrite").parquet(output_path)
        
        output_count = customer_ltv_df.count()
        logging.info(f"[Stage: build_customer_ltv] output_count: {output_count:,} rows")
        
    except Exception as e:
        logging.error(f"Error in build_customer_ltv: {e}")
        raise

def build_daily_summary(spark, silver_path, output_path, run_date):
    try:
        logging.info("Starting build_daily_summary stage")
        silver_df = spark.read.parquet(silver_path).filter(col("transaction_date") == run_date)  # Partition pruning
        
        daily_summary_df = (silver_df
           .groupBy("transaction_date")
           .agg(
                sum(when(col("status") == "COMPLETED", col("amount")).otherwise(lit(0))).alias("total_revenue"),
                count("*").alias("total_txns"),
                countDistinct("customer_id").alias("unique_customers"),
                countDistinct("merchant_id").alias("unique_merchants"),
                (count(when(col("status") == "FAILED", 1)) / count("*") * 100).alias("failure_rate_pct")
            ))
        
        partition_path = f"{output_path}/transaction_date={run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        daily_summary_df.write.mode("overwrite").partitionBy("transaction_date").parquet(output_path)
        
        output_count = spark.read.parquet(output_path).where(col("transaction_date") == run_date).count()
        logging.info(f"[Stage: build_daily_summary] output_count: {output_count:,} rows")
        
    except Exception as e:
        logging.error(f"Error in build_daily_summary: {e}")
        raise

def run_gold(spark, silver_path, gold_output_dir, run_date):
    try:
        logging.info("Starting run_gold stage")
        merchant_performance_output_path = f"{gold_output_dir}/merchant_performance"
        customer_ltv_output_path = f"{gold_output_dir}/customer_ltv"
        daily_summary_output_path = f"{gold_output_dir}/daily_summary"
        
        build_merchant_performance(spark, silver_path, merchant_performance_output_path, run_date)
        build_customer_ltv(spark, silver_path, customer_ltv_output_path)
        build_daily_summary(spark, silver_path, daily_summary_output_path, run_date)
        
        merchant_performance_rows = spark.read.parquet(merchant_performance_output_path).count()
        customer_ltv_rows = spark.read.parquet(customer_ltv_output_path).count()
        daily_summary_rows = spark.read.parquet(daily_summary_output_path).count()
        
        run_metadata = {
            "run_date": run_date,
            "merchant_performance_rows": merchant_performance_rows,
            "customer_ltv_rows": customer_ltv_rows,
            "daily_summary_rows": daily_summary_rows
        }
        
        spark.sparkContext.parallelize([run_metadata]).write.json(f"{gold_output_dir}/run_metadata.json")
        
    except Exception as e:
        logging.error(f"Error in run_gold: {e}")
        raise

def main():
    try:
        logging.info("Pipeline started")
        spark = (SparkSession.builder
                .appName("Sigma DataTech Transaction Analytics Pipeline")
                 .getOrCreate())

        input_path = "s3://sigma-datatech/raw/transactions.csv"
        merchants_path = "s3://sigma-datatech/raw/merchants.csv"
        bronze_output_path = "s3://sigma-datatech/bronze/"
        silver_output_path = "s3://sigma-datatech/silver/"
        gold_output_path = "s3://sigma-datatech/gold/"
        run_date = "2026-05-27"
        run_id = "run_id_20260527"
        started_at = datetime.now().isoformat()

        ingest_bronze(spark, input_path, bronze_output_path, run_date, run_id)
        transform_silver(spark, f"{bronze_output_path}/ingestion_timestamp={run_date}", merchants_path, silver_output_path, run_date)
        run_gold(spark, silver_output_path, gold_output_path, run_date)

        completed_at = datetime.now().isoformat()
        run_metadata = {
            "pipeline_name": "Sigma DataTech Transaction Analytics Pipeline",
            "run_date": run_date,
            "run_id": run_id,
            "run_status": "SUCCESS",
            "started_at": started_at,
            "completed_at": completed_at
        }

        with open(f"s3://sigma-datatech/metadata/run_metadata_{run_date}.json", "w") as f:
            json.dump(run_metadata, f)
            
    except Exception as e:
        completed_at = datetime.now().isoformat()
        run_metadata = {
            "pipeline_name": "Sigma DataTech Transaction Analytics Pipeline",
            "run_date": run_date,
            "run_id": run_id,
            "run_status": "FAILED",
            "error_message": str(e),
            "started_at": started_at,
            "completed_at": completed_at
        }

        with open(f"s3://sigma-datatech/metadata/run_metadata_{run_date}.json", "w") as f:
            json.dump(run_metadata, f)
        
        raise

if __name__ == "__main__":
    main()
