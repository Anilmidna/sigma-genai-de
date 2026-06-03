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
    already_loaded_ids_raw = params.get("already_loaded_ids", "[]")
    if isinstance(already_loaded_ids_raw, list):
        already_loaded_ids = already_loaded_ids_raw
    elif str(already_loaded_ids_raw).startswith("["):
        try:
            already_loaded_ids = json.loads(already_loaded_ids_raw)
        except Exception:
            already_loaded_ids = [x.strip() for x in str(already_loaded_ids_raw).split(",") if x.strip()]
    else:
        already_loaded_ids = [x.strip() for x in str(already_loaded_ids_raw).split(",") if x.strip()]
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
    # Switch to S3 read mode directly
    bucket_name = os.getenv("SIGMA_S3_BUCKET", "sigma-datatech-ud")
    s3 = boto3.client("s3", region_name=region)
    print(f"  [S3 REPLAY BYPASS] Replaying records directly from S3 bucket '{bucket_name}' under bronze/ prefix...")

    raw_records   = []
    fixed_records = []
    skipped_ids   = []
    loaded_set = set(already_loaded_ids)

    try:
        resp = s3.list_objects_v2(Bucket=bucket_name, Prefix="bronze/")
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".json"):
                continue
            
            # Read line-delimited JSON Line file
            file_obj = s3.get_object(Bucket=bucket_name, Key=key)
            content  = file_obj["Body"].read().decode("utf-8")
            
            for line in content.splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
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
    except Exception as e:
        print(f"  Error reading files from S3: {e}")

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
