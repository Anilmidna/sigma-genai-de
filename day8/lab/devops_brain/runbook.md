# Pipeline Overview

This pipeline processes transaction data, transforms it into a cleaned and enriched format, and computes merchant performance and daily summaries. It runs to ensure data integrity and provide actionable insights. If it stops, data reporting and analytics will be incomplete.

## Pipeline Steps

1. Connect to the DuckDB database using `get_connection()`.
2. Set up necessary tables using `setup_tables(con)`.
3. Load merchant data into the database using `load_merchants(con)`.
4. Load raw transactions into the bronze table using `load_bronze(con, transactions)`.
5. Transform bronze transactions to silver transactions using `transform_bronze_to_silver(transactions, merchants)`.
6. Load transformed transactions into the silver table using `load_silver(con, silver_rows)`.
7. Compute merchant performance metrics using `compute_merchant_performance(silver_rows)`.
8. Compute daily summary metrics using `compute_daily_summary(silver_rows)`.
9. Load computed metrics into the gold tables using `load_gold(con, merchant_perf, daily_summary)`.

## Schedule / Trigger

The pipeline runs every day at 2 AM UTC. It is triggered by a cron job.

## Failure Modes

1. **DuckDB Connection Failure**
   - **Root Cause:** Database server is down.
   - **Symptom:** `get_connection()` fails.
2. **Table Creation Error**
   - **Root Cause:** SQL syntax error in `setup_tables(con)`.
   - **Symptom:** Table creation fails.
3. **Merchant Data Load Failure**
   - **Root Cause:** Corrupt merchant data.
   - **Symptom:** `load_merchants(con)` throws an exception.
4. **Bronze Table Load Failure**
   - **Root Cause:** Malformed transaction data.
   - **Symptom:** `load_bronze(con, transactions)` fails.
5. **Silver Table Transformation Failure**
   - **Root Cause:** Missing merchant data for transactions.
   - **Symptom:** `transform_bronze_to_silver(transactions, merchants)` produces incomplete data.

## Recovery Actions

1. **DuckDB Connection Failure**
   - Check database server status.
   - Restart the database server if necessary.
   - Retry the pipeline.
2. **Table Creation Error**
   - Review and correct the SQL in `setup_tables(con)`.
   - Rerun the pipeline.
3. **Merchant Data Load Failure**
   - Validate and correct the merchant data.
   - Retry `load_merchants(con)`.
4. **Bronze Table Load Failure**
   - Inspect and correct the transaction data.
   - Retry `load_bronze(con, transactions)`.
5. **Silver Table Transformation Failure**
   - Ensure all merchants are loaded.
   - Retry `transform_bronze_to_silver(transactions, merchants)`.

## Known Bugs

- Hardcoded AWS credentials in the source code.
- Lack of null handling in `transform_bronze_to_silver(transactions, merchants)`.

## Escalation Contacts

1. **On-call DE:** Priya Nair (priya.nair@sigmadatatech.in, +91-98400-11111)
2. **Tech Lead:** Arjun Mehta (arjun.mehta@sigmadatatech.in)
3. **Platform Manager:** Kavya Reddy (kavya.reddy@sigmadatatech.in)

## Data Quality Checks

- Verify the number of records in `silver_transactions`.
- Check for null values in `silver_transactions`.
- Ensure `gold_merchant_performance` and `gold_daily_summary` tables are populated.
- Confirm the correctness of computed metrics in `gold_merchant_performance` and `gold_daily_summary`.