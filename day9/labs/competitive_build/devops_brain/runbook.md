# Pipeline Overview

This pipeline processes transaction data, transforming it from raw (bronze) to cleaned (silver) and finally to aggregated (gold) tables. It runs to ensure data is available for downstream analytics and reporting. If this pipeline fails, critical business metrics and reports will be inaccurate or missing.

## Pipeline Steps

1. Connect to the DuckDB database using `get_connection`.
2. Set up necessary tables using `setup_tables`.
3. Load merchant data into the `merchants` table using `load_merchants`.
4. Load all transactions into the `bronze_transactions` table using `load_bronze`.
5. Transform bronze transactions to silver using `transform_bronze_to_silver`.
6. Load transformed data into the `silver_transactions` table using `load_silver`.
7. Compute merchant performance metrics using `compute_merchant_performance`.
8. Compute daily summary metrics using `compute_daily_summary`.
9. Load computed metrics into the `gold_merchant_performance` and `gold_daily_summary` tables using `load_gold`.

## Schedule / Trigger

This pipeline is scheduled to run every night at 2 AM using a cron job.

## Failure Modes

1. **Database Connection Failure**
   - **Root Cause:** DuckDB service is down.
   - **Symptom:** `get_connection` fails.
2. **Table Creation Error**
   - **Root Cause:** SQL syntax error in `setup_tables`.
   - **Symptom:** Table creation fails.
3. **Merchant Data Load Failure**
   - **Root Cause:** Corrupted merchant data.
   - **Symptom:** `load_merchants` throws an exception.
4. **Bronze Data Load Failure**
   - **Root Cause:** Malformed transaction data.
   - **Symptom:** `load_bronze` fails to insert records.
5. **Silver Transformation Failure**
   - **Root Cause:** Missing merchant IDs in transactions.
   - **Symptom:** `transform_bronze_to_silver` produces incomplete data.

## Recovery Actions

1. **Database Connection Failure**
   - Check DuckDB service status.
   - Restart the service if necessary.
   - Retry the pipeline.
2. **Table Creation Error**
   - Review and correct the SQL in `setup_tables`.
   - Rerun the pipeline.
3. **Merchant Data Load Failure**
   - Validate and correct the merchant data.
   - Rerun `load_merchants`.
4. **Bronze Data Load Failure**
   - Inspect and correct the transaction data.
   - Rerun `load_bronze`.
5. **Silver Transformation Failure**
   - Ensure all transactions have valid merchant IDs.
   - Rerun `transform_bronze_to_silver`.

## Known Bugs

- Hardcoded AWS credentials in the source code.
- Lack of null handling in `transform_bronze_to_silver`.

## Escalation Contacts

1. **On-call DE:** Priya Nair (priya.nair@sigmadatatech.in, +91-98400-11111)
2. **Tech Lead:** Arjun Mehta (arjun.mehta@sigmadatatech.in)
3. **Platform Manager:** Kavya Reddy (kavya.reddy@sigmadatatech.in)

## Data Quality Checks

- Verify the count of records in `bronze_transactions`, `silver_transactions`, `gold_merchant_performance`, and `gold_daily_summary`.
- Ensure `quality_flag` is set correctly in `silver_transactions`.
- Check for missing or incorrect merchant names in `silver_transactions`.
- Validate the computed metrics in `gold_merchant_performance` and `gold_daily_summary`.