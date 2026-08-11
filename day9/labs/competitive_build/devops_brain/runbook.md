## Pipeline Overview

This pipeline ingests transaction data, transforms it, and loads it into bronze, silver, and gold tables. It also computes merchant performance and daily summaries. If this pipeline stops, downstream analytics and reporting will be impacted.

## Pipeline Steps

1. Connect to DuckDB using `get_connection()`.
2. Set up tables using `setup_tables()`.
3. Load merchants using `load_merchants()`.
4. Load transactions into bronze using `load_bronze()`.
5. Transform bronze to silver using `transform_bronze_to_silver()`.
6. Load silver transactions using `load_silver()`.
7. Compute merchant performance using `compute_merchant_performance()`.
8. Compute daily summary using `compute_daily_summary()`.
9. Load gold tables using `load_gold()`.

## Schedule / Trigger

This pipeline runs every night at 2 AM UTC via a cron job.

## Failure Modes

1. **Database Connection Failure**
   - **Root Cause:** DuckDB service is down.
   - **Symptom:** `get_connection()` fails.
2. **Table Creation Failure**
   - **Root Cause:** Syntax error in SQL.
   - **Symptom:** `setup_tables()` throws an exception.
3. **Merchant Data Load Failure**
   - **Root Cause:** Corrupt merchant data.
   - **Symptom:** `load_merchants()` fails.
4. **Bronze Load Failure**
   - **Root Cause:** Invalid transaction data.
   - **Symptom:** `load_bronze()` fails.
5. **Silver Transformation Failure**
   - **Root Cause:** Missing merchant ID in transactions.
   - **Symptom:** `transform_bronze_to_silver()` fails.

## Recovery Actions

1. **Database Connection Failure**
   - Check DuckDB service status.
   - Restart DuckDB if necessary.
   - Retry `get_connection()`.
2. **Table Creation Failure**
   - Review SQL syntax in `setup_tables()`.
   - Correct the syntax and retry.
3. **Merchant Data Load Failure**
   - Inspect `MERCHANTS` data for corruption.
   - Clean the data and retry `load_merchants()`.
4. **Bronze Load Failure**
   - Validate `TRANSACTIONS_CLEAN` and `TRANSACTIONS_DIRTY` data.
   - Correct invalid data and retry `load_bronze()`.
5. **Silver Transformation Failure**
   - Ensure all transactions have a valid `merchant_id`.
   - Clean the data and retry `transform_bronze_to_silver()`.

## Known Bugs

- Hardcoded AWS credentials in the code.
- Lack of null handling in `transform_bronze_to_silver()`.

## Escalation Contacts

1. **On-call DE:** Priya Nair (priya.nair@sigmadatatech.in, +91-98400-11111)
2. **Tech Lead:** Arjun Mehta (arjun.mehta@sigmadatatech.in)
3. **Platform Manager:** Kavya Reddy (kavya.reddy@sigmadatatech.in)

## Data Quality Checks

- Verify the number of records in `bronze_transactions`, `silver_transactions`, `gold_merchant_performance`, and `gold_daily_summary`.
- Ensure `quality_flag` is set correctly in `silver_transactions`.
- Check for duplicate `transaction_id` in `silver_transactions`.
- Validate `total_revenue` and `txn_count` in `gold_merchant_performance`.
- Confirm `unique_customers` and `unique_merchants` in `gold_daily_summary`.