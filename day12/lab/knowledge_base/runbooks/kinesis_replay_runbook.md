# Runbook — Kinesis Replay with Idempotent Recovery

**Use when:** Records reached Kinesis but did not load to Snowflake.
**Do NOT use:** If records were lost before Kinesis (throttling at source).

## Pre-conditions
1. Root cause must be identified and fixed BEFORE replay.
   Replaying into a broken pipeline re-introduces the problem.
2. The Lambda LIVE alias must point to the stable version.
   Confirm: `aws lambda get-alias --function-name sigma-kinesis-producer --name LIVE`

## Steps

### Step 1 — Determine the exact failure window
Use the Forensics Agent output: `anomaly_window.detected_at`
This is the timestamp to start the shard iterator from.

### Step 2 — Get already-loaded transaction IDs
```sql
SELECT transaction_id
FROM SIGMA.SILVER.TRANSACTIONS
WHERE _loaded_at >= '[failure_start_timestamp]'
```
Pass this list to get_kinesis_records as `already_loaded_ids`.

### Step 3 — Replay from shard iterator
Call `get_kinesis_records` with:
- `start_timestamp`: failure start from step 1
- `already_loaded_ids`: list from step 2
- `shard_id`: shardId-000000000000 (default for 1-shard stream)

The tool returns `records` (clean, field-remapped) and `duplicates_skipped`.

### Step 4 — Quality gate before loading
Split records:
- Clean: transaction_id not null, amount > 0, transaction_date matches YYYY-MM-DD
- Quarantine: any record that fails

### Step 5 — Load clean records
Call `load_to_snowflake` with the clean records.
The MERGE INTO on transaction_id provides a second layer of deduplication.

### Step 6 — Verify
```sql
SELECT COUNT(*) FROM SIGMA.SILVER.TRANSACTIONS
WHERE _loaded_at >= '[recovery_start_timestamp]'
```
Must match the `rows_loaded` count returned by load_to_snowflake.

## Kinesis Retention
Default retention: 24 hours.
Extended retention (7 days): enabled for sigma-transactions stream.
Records from up to 7 days ago can be replayed.

## Idempotency Guarantee
Two mechanisms protect against duplicates:
1. `already_loaded_ids` filters at the Kinesis read step
2. `MERGE INTO ON transaction_id` at the Snowflake write step
Running this recovery twice produces zero duplicate rows.
