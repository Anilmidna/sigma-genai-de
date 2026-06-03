# Pipeline Overview

This pipeline processes transaction data, enriches it with merchant information, and computes merchant performance and daily summaries. It runs to ensure up-to-date analytics for business insights. If it stops, real-time analytics and reporting will be impacted.

## Pipeline Steps

1. Connect to the DuckDB database using `get_connection()`.
2. Set up necessary tables using `setup_tables(con)`.
3. Load merchant data into the `merchants` table using `load_merchants(con)`.
4. Load transaction data into the `bronze_transactions` table using `load_bronze(con, transactions)`.
5. Transform bronze transactions to silver transactions using `transform_bronze_to_silver(transactions, merchants)`.
6. Load transformed data into the `silver_transactions` table using `load_silver(con, silver_rows)`.
7. Compute merchant performance metrics using `compute_merchant_performance(silver_rows)`.
8. Compute daily summary metrics using `compute_daily_summary(silver_rows)`.
9. Load computed metrics into the `gold_merchant_performance` and `gold_daily_summary` tables using `load_gold(con, merchant_perf, daily_summary)`.

## Schedule / Trigger

This pipeline runs every hour, triggered by a cron job.

## Failure Modes

1. **Database Connection Failure**
   - **Root Cause:** DuckDB service is down.
   - **Symptom:** `get_connection()` fails.
2. **Table Setup Error**
   - **Root Cause:** SQL syntax error in `setup_tables(con)`.
   - **Symptom:** Table creation fails.
3. **Merchant Data Load Failure**
   - **Root Cause:** Corrupted merchant data.
   - **Symptom:** `load_merchants(con)` throws an exception.
4. **Bronze Transaction Load Failure**
   - **Root Cause:** Malformed transaction data.
   - **Symptom:** `load_bronze(con, transactions)` fails.
5. **Silver Transformation Failure**
   - **Root Cause:** Missing merchant information for transactions.
   - **Symptom:** `transform_bronze_to_silver(transactions, merchants)` produces incomplete data.

## Recovery Actions

1. **Database Connection Failure**
   - Check DuckDB service status.
   - Restart the service if necessary.
   - Retry the pipeline.
2. **Table Setup Error**
   - Review and correct the SQL in `setup_tables(con)`.
   - Rerun the pipeline.
3. **Merchant Data Load Failure**
   - Validate merchant data integrity.
   - Correct any issues and rerun `load_merchants(con)`.
4. **Bronze Transaction Load Failure**
   - Inspect transaction data for errors.
   - Correct data and retry `load_bronze(con, transactions)`.
5. **Silver Transformation Failure**
   - Ensure all merchants are correctly loaded.
   - Rerun `transform_bronze_to_silver(transactions, merchants)`.

## Known Bugs

- Hardcoded AWS credentials in the source code.
- Lack of null handling in `transform_bronze_to_silver(transactions, merchants)`.

## Escalation Contacts

1. **On-call DE:** Priya Nair (priya.nair@sigmadatatech.in, +91-98400-11111)
2. **Tech Lead:** Arjun Mehta (arjun.mehta@sigmadatatech.in)
3. **Platform Manager:** Kavya Reddy (kavya.reddy@sigmadatatech.in)

## Data Quality Checks

- Verify the count of records in `bronze_transactions`, `silver_transactions`, `gold_merchant_performance`, and `gold_daily_summary`.
- Ensure `quality_flag` is correctly set in `silver_transactions`.
- Check for any NULL values in critical fields.
- Validate the computed metrics in `gold_merchant_performance` and `gold_daily_summary`.