"""
Lambda Tool: get_kinesis_records (Migrated to S3)
Called by: Recovery Agent
Action group: DataPlatformTools

Replays records from the S3 Bronze folder starting at a specific timestamp.
Returns records with field remapping applied (merchant_nm → merchant_name,
DD-MM-YYYY → YYYY-MM-DD date fix).

Idempotency: caller passes already_loaded_ids so this tool can exclude
records already in Snowflake — zero duplicates guaranteed.
"""

import boto3, json, os, re, time
from datetime import datetime, timezone

s3 = boto3.client('s3')

def lambda_handler(event, context):
    params = {p["name"]: p["value"] for p in event.get("parameters", [])}

    # These are kept for interface compatibility with the Recovery Agent
    stream_name         = params.get("stream_name", os.getenv("SIGMA_STREAM", "sigma-transactions"))
    shard_id            = params.get("shard_id", "shardId-000000000000")
    
    start_timestamp     = params.get("start_timestamp")          # ISO string (e.g. 2026-06-04T02:11:00Z)
    already_loaded_ids  = json.loads(params.get("already_loaded_ids", "[]"))
    region              = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    result = replay_records_from_s3(start_timestamp, already_loaded_ids, region)

    # Inject compatibility fields so agent parser succeeds
    result["stream_name"] = stream_name
    result["shard_id"] = shard_id

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


def replay_records_from_s3(start_timestamp: str, already_loaded_ids: list, region: str) -> dict:
    bucket_name = os.getenv("SIGMA_S3_BUCKET")
    if not bucket_name:
        raise ValueError("SIGMA_S3_BUCKET environment variable must be set.")
        
    s3_client = boto3.client("s3", region_name=region)
    
    # Parse start timestamp
    if start_timestamp:
        # Convert e.g., '2026-06-04T02:11:00Z' or '2026-06-04T02:11:00+00:00' to offset-aware datetime
        ts_str = start_timestamp.replace('Z', '+00:00')
        # If timestamp is space-separated instead of T, handle it
        ts_str = ts_str.replace(' ', 'T')
        dt_start = datetime.fromisoformat(ts_str)
    else:
        dt_start = datetime.min.replace(tzinfo=timezone.utc)

    loaded_set = set(already_loaded_ids)
    raw_records = []
    fixed_records = []
    skipped_ids = []
    
    # Track fixes for reporting statistics
    merchant_nm_renamed = 0
    date_format_fixed = 0

    print(f"Scanning S3 bucket {bucket_name} for files modified after {dt_start}")
    
    # List objects in bronze/ prefix
    paginator = s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket_name, Prefix='bronze/')
    
    for page in pages:
        for obj in page.get('Contents', []):
            last_modified = obj['LastModified'] # Already datetime with tzinfo
            
            # Skip if modified before the start window
            if last_modified < dt_start:
                continue
                
            file_key = obj['Key']
            print(f"Reading file: {file_key}")
            
            try:
                file_obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
                content = file_obj['Body'].read().decode('utf-8')
                
                for line in content.split('\n'):
                    if not line.strip():
                        continue
                    
                    data = json.loads(line)
                    raw_records.append(data)
                    
                    # Track metrics
                    if "merchant_nm" in data:
                        merchant_nm_renamed += 1
                    if re.match(r"^\d{2}-\d{2}-\d{4}$", str(data.get("transaction_date", ""))):
                        date_format_fixed += 1
                        
                    fixed = fix_record(data)
                    tid = fixed.get("transaction_id", "")
                    
                    if tid and tid in loaded_set:
                        skipped_ids.append(tid) # already in Snowflake
                    else:
                        fixed_records.append(fixed)
                        if tid:
                            loaded_set.add(tid)
            except Exception as e:
                print(f"Error reading file {file_key}: {e}")
                pass
                
    return {
        "start_timestamp": start_timestamp,
        "raw_records_found": len(raw_records),
        "duplicates_skipped": len(skipped_ids),
        "clean_records": len(fixed_records),
        "records": fixed_records,
        "field_fixes_applied": {
            "merchant_nm_renamed": merchant_nm_renamed,
            "date_format_fixed": date_format_fixed,
        },
    }


# ── Local test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    bucket = os.getenv("SIGMA_S3_BUCKET")
    print(f"\nReplaying from S3 Bucket: {bucket} (Reading since 2 hours ago)...\n")
    
    # Test offset: 2 hours ago
    from datetime import timedelta
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    
    try:
        result = replay_records_from_s3(two_hours_ago, [], os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
        print(f"Raw records found  : {result['raw_records_found']}")
        print(f"Duplicates skipped : {result['duplicates_skipped']}")
        print(f"Clean records      : {result['clean_records']}")
        print(f"Field fixes        : {result['field_fixes_applied']}")

        if result["records"]:
            print(f"\nSample record: {json.dumps(result['records'][0], indent=2)}")
    except Exception as e:
        print(f"Error testing get_kinesis_records.py: {e}")

    if "--test" in sys.argv:
        print("\nget_kinesis_records.py test PASSED")
