import logging
import shutil
from datetime import datetime
from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import col, lit, coalesce, sum, count, max, broadcast, when, avg, first, last, mode
from pyspark.sql.types import FloatType, StringType, DateType

logging.basicConfig(level=logging.INFO)

def ingest_bronze(spark, input_path, output_path, run_date, run_id):
    try:
        logging.info("Starting Bronze layer ingestion")
        transactions_df = (spark.read.format("csv")
                          .option("header", "true")
                          .option("inferSchema", "false")
                          .load(input_path))
        
        transactions_df = (transactions_df.withColumn("ingestion_timestamp", lit(run_date))
                           .withColumn("source_file", lit("transactions.csv"))
                          .withColumn("pipeline_run_id", lit(run_id)))
        
        partition_path = f"{output_path}/{run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        
        transactions_df.write.partitionBy("ingestion_timestamp").parquet(output_path)
        logging.info("[Stage: Bronze] Output: %s rows", transactions_df.count())
    except Exception as e:
        logging.error("[Stage: Bronze] Error: %s", e)
        raise

def transform_silver(spark, bronze_path, merchants_path, output_path, run_date):
    try:
        logging.info("Starting Silver layer transformation")
        transactions_df = (spark.read.format("parquet")
                          .load(bronze_path)
                          .where(col("ingestion_timestamp") == run_date))
        
        transactions_df = (transactions_df.withColumn("amount", col("amount").cast(FloatType()))
                          .withColumn("transaction_date", col("transaction_date").cast(DateType()))
                          .withColumn("transaction_id", col("transaction_id").cast(StringType()))
                          .withColumn("merchant_id", col("merchant_id").cast(StringType())))
        
        logging.info("[Stage: Silver] Input: %s rows", transactions_df.count())
        
        transactions_df = transactions_df.filter((col("transaction_id").isNotNull()) & (col("amount") >= 0))
        logging.info("[Stage: Silver] After filter: %s rows", transactions_df.count())
        
        window = Window.partitionBy("transaction_id")
        deduped_transactions_df = (transactions_df.withColumn("rank", 
                       max(col("ingestion_timestamp")).over(window))
                                   .filter(col("rank") == col("ingestion_timestamp"))
                                    .drop("rank"))
        logging.info("[Stage: Silver] After dedup: %s rows", deduped_transactions_df.count())
        
        merchants_df = (spark.read.format("csv")
                        .option("header", "true")
                        .option("inferSchema", "false")
                       .load(merchants_path))
        merchants_df = merchants_df.cache()
        
        enriched_transactions_df = (deduped_transactions_df.join(broadcast(merchants_df), 
                                                                 deduped_transactions_df.merchant_id == merchants_df.merchant_id, 
                                                                 "left_outer"))
        
        enriched_transactions_df = (enriched_transactions_df.withColumn("quality_flag", 
                                                                         coalesce(merchants_df.merchant_name, lit("UNMATCHED"))))
        
        partition_path = f"{output_path}/{run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        
        enriched_transactions_df.write.partitionBy("transaction_date").parquet(output_path)
        logging.info("[Stage: Silver] Output: %s rows", enriched_transactions_df.count())
    except Exception as e:
        logging.error("[Stage: Silver] Error: %s", e)
        raise

def build_merchant_performance(spark, silver_path, output_path, run_date):
    try:
        logging.info("Starting Gold layer - merchant performance")
        silver_transactions = spark.read.parquet(silver_path).where(col("transaction_date") == run_date)
        
        silver_merchants = spark.read.parquet(f"{silver_path}/merchants").cache()
        
        transactions_with_merchants = silver_transactions.join(broadcast(silver_merchants), "merchant_id")
        
        merchant_performance = transactions_with_merchants.groupBy("merchant_id", "merchant_name", "category", "city", "transaction_date") \
            .agg(
                sum(when(col("status") == "COMPLETED", col("amount")).otherwise(0)).alias("total_revenue"),
                count("*").alias("txn_count"),
                (count(when(col("status") == "FAILED", 1)) / count("*") * 100).alias("failure_rate_pct")
            )
        
        partition_path = f"{output_path}/{run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        
        merchant_performance.write.mode("overwrite").partitionBy("transaction_date").parquet(output_path)
        logging.info("[Stage: Gold - Merchant Performance] Output: %s rows", merchant_performance.count())
    except Exception as e:
        logging.error("[Stage: Gold - Merchant Performance] Error: %s", e)
        raise

def build_customer_ltv(spark, silver_path, output_path):
    try:
        logging.info("Starting Gold layer - customer LTV")
        silver_transactions = spark.read.parquet(silver_path)
        
        customer_ltv = silver_transactions.filter(col("status") == "COMPLETED") \
           .groupBy("customer_id") \
           .agg(
                sum("amount").alias("total_spent"),
                count("*").alias("total_txns"),
                avg("amount").alias("avg_txn_value"),
                first("transaction_date").alias("first_txn_date"),
                last("transaction_date").alias("last_txn_date"),
                coalesce(mode("payment_method").over(Window.partitionBy("customer_id")), lit(None)).alias("preferred_payment_method")
            )
        
        partition_path = output_path
        shutil.rmtree(partition_path, ignore_errors=True)
        
        customer_ltv.write.mode("overwrite").parquet(output_path)
        logging.info("[Stage: Gold - Customer LTV] Output: %s rows", customer_ltv.count())
    except Exception as e:
        logging.error("[Stage: Gold - Customer LTV] Error: %s", e)
        raise

def build_daily_summary(spark, silver_path, output_path, run_date):
    try:
        logging.info("Starting Gold layer - daily summary")
        silver_transactions = spark.read.parquet(silver_path).where(col("transaction_date") == run_date)
        
        daily_summary = silver_transactions.groupBy("transaction_date") \
           .agg(
                sum(when(col("status") == "COMPLETED", col("amount"))).alias("total_revenue"),
                count("*").alias("total_txns"),
                count(col("customer_id").distinct()).alias("unique_customers"),
                count(col("merchant_id").distinct()).alias("unique_merchants"),
                (count(when(col("status") == "FAILED", 1)) / count("*") * 100).alias("failure_rate_pct")
            )
        
        partition_path = f"{output_path}/{run_date}"
        shutil.rmtree(partition_path, ignore_errors=True)
        
        daily_summary.write.mode("overwrite").partitionBy("transaction_date").parquet(output_path)
        logging.info("[Stage: Gold - Daily Summary] Output: %s rows", daily_summary.count())
    except Exception as e:
        logging.error("[Stage: Gold - Daily Summary] Error: %s", e)
        raise

def run_gold(spark, silver_path, gold_output_dir, run_date):
    try:
        logging.info("Starting Gold layer aggregation")
        run_metadata = {
            "run_date": run_date,
            "silver_path": silver_path,
            "gold_output_dir": gold_output_dir,
            "tables": []
        }
        
        started_at = datetime.now().isoformat()
        
        build_merchant_performance(spark, silver_path, f"{gold_output_dir}/merchant_performance", run_date)
        build_customer_ltv(spark, silver_path, f"{gold_output_dir}/customer_ltv")
        build_daily_summary(spark, silver_path, f"{gold_output_dir}/daily_summary", run_date)
        
        completed_at = datetime.now().isoformat()
        
        run_metadata["started_at"] = started_at
        run_metadata["completed_at"] = completed_at
        run_metadata["run_status"] = "SUCCESS"
        
        spark.sparkContext.parallelize([run_metadata]).write.json(f"{gold_output_dir}/run_metadata")
    except Exception as e:
        logging.error("[Stage: Gold] Error: %s", e)
        run_metadata["run_status"] = "FAILED"
        run_metadata["error_message"] = str(e)
        spark.sparkContext.parallelize([run_metadata]).write.json(f"{gold_output_dir}/run_metadata")
        raise

def main():
    spark = (SparkSession.builder
            .appName("Sigma DataTech Transaction Analytics Pipeline")
             .getOrCreate())
    
    input_path = "s3://sigma-datatech-transactions/bronze/"
    bronze_path = "s3://sigma-datatech-transactions/silver/"
    silver_path = "s3://sigma-datatech-transactions/gold/"
    merchants_path = "s3://sigma-datatech-merchants/merchants.csv"
    run_date = "2026-05-27"
    run_id = "run_id_12345"
    
    try:
        ingest_bronze(spark, input_path, f"{bronze_path}", run_date, run_id)
        transform_silver(spark, f"{bronze_path}/{run_date}", merchants_path, f"{silver_path}", run_date)
        run_gold(spark, f"{silver_path}/{run_date}", f"{silver_path}/gold", run_date)
    except Exception as e:
        logging.error("Pipeline failed: %s", e)
        raise

if __name__ == "__main__":
    main()
