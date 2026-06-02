"""
Lambda Tool: get_kinesis_records
Called by: Recovery Agent
Action group: DataPlatformTools

Replays records from a Kinesis shard starting at a specific timestamp.
Returns records with field remapping applied (merchant_nm → merchant_name,
DD-MM-YYYY → YYYY-MM-DD date fix).

Idempotency: caller passes already_loaded_ids so this tool can exclude
records already in Snowflake — zero duplicates guaranteed.
"""

import boto3, json, os, re, time
from datetime import datetime, timezone


def lambda_handler(event, context):
    params = {p["name"]: p["value"] for p in event.get("parameters", [])}

    stream_name         = params.get("stream_name", os.getenv("SIGMA_STREAM", "sigma-transactions"))
    shard_id            = params.get("shard_id", "shardId-000000000000")
    start_timestamp     = params.get("start_timestamp")          # ISO string
    already_loaded_ids  = json.loads(params.get("already_loaded_ids", "[]"))
    region              = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    result = replay_records(stream_name, shard_id, start_timestamp,
                            already_loaded_ids, region)

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "function": event.get("function"),
            "functionResponse": {
                "responseBody": {"TEXT": {"body": json.dumps(result, default=str)}}
            },
        },
    }


def fix_record(record: dict) -> dict:
    """
    Apply field remapping introduced by the broken Lambda v2.
    merchant_nm  → merchant_name  (field was renamed in v2)
    DD-MM-YYYY   → YYYY-MM-DD    (date format changed in v2)
    """
    fixed = dict(record)

    # Fix field rename
    if "merchant_nm" in fixed and "merchant_name" not in fixed:
        fixed["merchant_name"] = fixed.pop("merchant_nm")

    # Fix date format
    date_val = fixed.get("transaction_date", "")
    if re.match(r"^\d{2}-\d{2}-\d{4}$", str(date_val)):
        parts = str(date_val).split("-")
        fixed["transaction_date"] = f"{parts[2]}-{parts[1]}-{parts[0]}"

    return fixed


def replay_records(stream_name: str, shard_id: str, start_timestamp: str,
                   already_loaded_ids: list, region: str) -> dict:
    kinesis = boto3.client("kinesis", region_name=region)

    # Get shard iterator at the exact failure timestamp
    iterator_args = {"StreamName": stream_name, "ShardId": shard_id}
    if start_timestamp:
        iterator_args["ShardIteratorType"] = "AT_TIMESTAMP"
        iterator_args["Timestamp"]          = start_timestamp
    else:
        iterator_args["ShardIteratorType"] = "TRIM_HORIZON"

    resp     = kinesis.get_shard_iterator(**iterator_args)
    iterator = resp["ShardIterator"]

    loaded_set = set(already_loaded_ids)
    raw_records   = []
    fixed_records = []
    skipped_ids   = []

    # Read up to 5 batches (Kinesis max 10MB per GetRecords call)
    for _ in range(5):
        batch = kinesis.get_records(ShardIterator=iterator, Limit=1000)
        for rec in batch["Records"]:
            try:
                data  = json.loads(rec["Data"].decode("utf-8"))
                raw_records.append(data)
                fixed = fix_record(data)
                tid   = fixed.get("transaction_id", "")

                if tid and tid in loaded_set:
                    skipped_ids.append(tid)    # already in Snowflake — skip
                else:
                    fixed_records.append(fixed)
                    if tid:
                        loaded_set.add(tid)
            except Exception:
                pass

        iterator = batch.get("NextShardIterator")
        if not iterator or not batch["Records"]:
            break
        time.sleep(0.2)    # Kinesis rate limit: 5 GetRecords/sec per shard

    return {
        "stream_name":       stream_name,
        "shard_id":          shard_id,
        "start_timestamp":   start_timestamp,
        "raw_records_found": len(raw_records),
        "duplicates_skipped": len(skipped_ids),
        "clean_records":     len(fixed_records),
        "records":           fixed_records,
        "field_fixes_applied": {
            "merchant_nm_renamed": sum(1 for r in raw_records if "merchant_nm" in r),
            "date_format_fixed":   sum(
                1 for r in raw_records
                if re.match(r"^\d{2}-\d{2}-\d{4}$",
                            str(r.get("transaction_date", "")))
            ),
        },
    }


# ── Local test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    stream = os.getenv("SIGMA_STREAM", "sigma-transactions")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    print(f"\nReplaying from {stream} (TRIM_HORIZON for test)...\n")
    result = replay_records(stream, "shardId-000000000000", None, [], region)

    print(f"Raw records found  : {result['raw_records_found']}")
    print(f"Duplicates skipped : {result['duplicates_skipped']}")
    print(f"Clean records      : {result['clean_records']}")
    print(f"Field fixes        : {result['field_fixes_applied']}")

    if result["records"]:
        print(f"\nSample record: {json.dumps(result['records'][0], indent=2)}")

    if "--test" in sys.argv:
        assert "records" in result
        print("\nget_kinesis_records.py test PASSED")
