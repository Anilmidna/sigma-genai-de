import shutil
import logging
from datetime import datetime
from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import col, lit, broadcast, when, sum, count, avg, min, max, first, coalesce
from pyspark.sql.types import StringType, FloatType, DateType

logging.basicConfig(level=logging.INFO)

def ingest_bronze(spark, input_path, output_path, run_date, run_id):
    try:
        logging.info("Starting ingest_bronze stage")
        partition_path = f"{output_path}/ingestion_timestamp={run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        
        transactions_df = (spark.read.format("csv")
                          .option("header", "true")
                          .option("inferSchema", "false")
                          .load(input_path))
        
        transactions_df = (transactions_df.withColumn("ingestion_timestamp", lit(run_date))
                           .withColumn("source_file", lit("transactions.csv"))
                          .withColumn("pipeline_run_id", lit(run_id)))
        
        transactions_df.write.mode("overwrite").partitionBy("ingestion_timestamp").parquet(output_path)
        
        logging.info(f"[Stage: ingest_bronze] output_count: {transactions_df.count():,} rows")
    except Exception as e:
        logging.error(f"Error in ingest_bronze: {e}")
        raise

def transform_silver(spark, bronze_path, merchants_path, output_path, run_date):
    try:
        logging.info("Starting transform_silver stage")
        partition_path = f"{output_path}/ingestion_timestamp={run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        
        transactions_df = (spark.read.format("parquet")
                           .load(bronze_path)
                          .filter(col("ingestion_timestamp") == run_date))  # Partition pruning
        
        transactions_df = transactions_df.withColumn("amount", col("amount").cast(FloatType()))
        transactions_df = transactions_df.withColumn("transaction_date", col("transaction_date").cast(DateType()))
        transactions_df = transactions_df.withColumn("transaction_id", col("transaction_id").cast(StringType()))
        transactions_df = transactions_df.withColumn("merchant_id", col("merchant_id").cast(StringType()))
        
        input_count = transactions_df.count()
        logging.info(f"[Stage: transform_silver] input_count: {input_count:,} rows")
        
        transactions_df = transactions_df.filter((col("transaction_id").isNotNull()) & (col("amount") >= 0))
        after_filter_count = transactions_df.count()
        logging.info(f"[Stage: transform_silver] after_filter_count: {after_filter_count:,} rows")
        
        transactions_df = transactions_df.sortWithinPartitions("transaction_id", "ingestion_timestamp", ascending=False).dropDuplicates(["transaction_id"], keep="first")
        after_dedup_count = transactions_df.count()
        logging.info(f"[Stage: transform_silver] after_dedup_count: {after_dedup_count:,} rows")
        
        merchants_df = (spark.read.format("csv")
                        .option("header", "true")
                       .option("inferSchema", "false")
                       .load(merchants_path))
        merchants_df = merchants_df.withColumn("merchant_id", col("merchant_id").cast(StringType()))
        merchants_df = merchants_df.cache()
        
        transactions_df = transactions_df.join(broadcast(merchants_df), on="merchant_id", how="left")
        
        transactions_df = transactions_df.withColumn("quality_flag", when(col("merchant_id").isNull(), "UNMATCHED").otherwise("CLEAN"))
        
        transactions_df.write.mode("overwrite").partitionBy("ingestion_timestamp").parquet(output_path)
        
        output_count = transactions_df.count()
        logging.info(f"[Stage: transform_silver] output_count: {output_count:,} rows")
    except Exception as e:
        logging.error(f"Error in transform_silver: {e}")
        raise

def build_merchant_performance(spark, silver_path, output_path, run_date):
    try:
        logging.info("Starting build_merchant_performance stage")
        partition_path = f"{output_path}/date={run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        
        silver_transactions = spark.read.parquet(silver_path).filter(col("ingestion_timestamp") == run_date)  # Partition pruning
        
        silver_merchants = spark.read.parquet(silver_path).filter(col("ingestion_timestamp") == run_date).cache()  # Partition pruning
        
        transactions_with_merchants = silver_transactions.join(
            broadcast(silver_merchants), silver_transactions["merchant_id"] == silver_merchants["merchant_id"], "left"
        )
        
        merchant_performance = transactions_with_merchants.groupBy("merchant_id", "merchant_name", "category", "city", "ingestion_timestamp") \
          .agg(
                sum(coalesce(col("amount").cast(FloatType()), 0)).alias("total_revenue"),
                count("*").alias("txn_count"),
                (count(when(col("status") == "FAILED", 1)) / count("*") * 100).alias("failure_rate_pct")
            ).filter(col("status") == "COMPLETED")
        
        merchant_performance.write.mode("overwrite").partitionBy("date").parquet(output_path)
    except Exception as e:
        logging.error(f"Error in build_merchant_performance: {e}")
        raise

def build_customer_ltv(spark, silver_path, output_path):
    try:
        logging.info("Starting build_customer_ltv stage")
        partition_path = output_path
        shutil.rmtree(partition_path, ignore_errors=True)
        
        silver_transactions = spark.read.parquet(silver_path)
        
        customer_ltv = silver_transactions.groupBy("customer_id") \
            .agg(
                sum(coalesce(col("amount").cast(FloatType()), 0)).alias("total_spent"),
                count("*").alias("total_txns"),
                avg(coalesce(col("amount").cast(FloatType()), 0)).alias("avg_txn_value"),
                min("transaction_date").alias("first_txn_date"),
                max("transaction_date").alias("last_txn_date"),
                first(col("payment_method")).over(Window.partitionBy("customer_id").orderBy(col("total_spent").desc())).alias("preferred_payment_method")
            ).filter(col("status") == "COMPLETED")
        
        customer_ltv.write.mode("overwrite").parquet(output_path)
    except Exception as e:
        logging.error(f"Error in build_customer_ltv: {e}")
        raise

def build_daily_summary(spark, silver_path, output_path, run_date):
    try:
        logging.info("Starting build_daily_summary stage")
        partition_path = f"{output_path}/date={run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        
        silver_transactions = spark.read.parquet(silver_path).filter(col("ingestion_timestamp") == run_date)  # Partition pruning
        
        daily_summary = silver_transactions.groupBy("ingestion_timestamp") \
           .agg(
                sum(coalesce(col("amount").cast(FloatType()), 0)).alias("total_revenue"),
                count("*").alias("total_txns"),
                countDistinct("customer_id").alias("unique_customers"),
                countDistinct("merchant_id").alias("unique_merchants"),
                (count(when(col("status") == "FAILED", 1)) / count("*") * 100).alias("failure_rate_pct")
            )
        
        daily_summary.write.mode("overwrite").partitionBy("date").parquet(output_path)
    except Exception as e:
        logging.error(f"Error in build_daily_summary: {e}")
        raise

def run_gold(spark, silver_path, gold_output_dir, run_date):
    try:
        logging.info("Starting run_gold stage")
        run_metadata = {
            "run_date": run_date,
            "silver_path": silver_path,
            "gold_output_dir": gold_output_dir,
            "tables": [],
            "started_at": datetime.now().isoformat(),
            "run_status": "SUCCESS",
            "error_message": None
        }
        
        merchant_performance_path = f"{gold_output_dir}/merchant_performance"
        customer_ltv_path = f"{gold_output_dir}/customer_ltv"
        daily_summary_path = f"{gold_output_dir}/daily_summary"
        
        build_merchant_performance(spark, silver_path, merchant_performance_path, run_date)
        build_customer_ltv(spark, silver_path, customer_ltv_path)
        build_daily_summary(spark, silver_path, daily_summary_path, run_date)
        
        run_metadata["tables"].extend(["merchant_performance", "customer_ltv", "daily_summary"])
        run_metadata["completed_at"] = datetime.now().isoformat()
        
        spark.sparkContext.parallelize([run_metadata]).write.json(f"{gold_output_dir}/run_metadata")
    except Exception as e:
        logging.error(f"Error in run_gold: {e}")
        run_metadata["run_status"] = "FAILED"
        run_metadata["error_message"] = str(e)
        spark.sparkContext.parallelize([run_metadata]).write.json(f"{gold_output_dir}/run_metadata")
        raise

def main():
    spark = (SparkSession.builder
            .appName("Sigma DataTech Transaction Analytics Pipeline")
             .getOrCreate())
    
    input_path = "s3://sigma-datatech/bronze/transactions/"
    bronze_path = "s3://sigma-datatech/silver/transactions/"
    merchants_path = "s3://sigma-datatech/bronze/merchants/"
    output_path = "s3://sigma-datatech/silver/transactions/"
    run_date = "2026-05-27"
    run_id = "run_id_20260527"
    
    try:
        ingest_bronze(spark, input_path, bronze_path, run_date, run_id)
        transform_silver(spark, bronze_path, merchants_path, output_path, run_date)
        gold_output_dir = "s3://sigma-datatech/gold/"
        run_gold(spark, output_path, gold_output_dir, run_date)
    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        raise

if __name__ == "__main__":
    main()
