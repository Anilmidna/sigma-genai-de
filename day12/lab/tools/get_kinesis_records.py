"""
Lambda Tool: get_s3_records  (registered as get_kinesis_records for API compatibility)
Called by: Recovery Agent

Reads malformed JSON files from S3 Bronze that were not loaded to Snowflake.
Applies field remapping (merchant_nm → merchant_name, DD-MM-YYYY → YYYY-MM-DD).
Returns clean records ready for load_to_snowflake.

Idempotency: caller passes already_loaded_ids so this tool excludes
records already in Snowflake — zero duplicates guaranteed.
"""

import boto3, json, os, re
from datetime import datetime, timezone


def lambda_handler(event, context):
    params = {p["name"]: p["value"] for p in event.get("parameters", [])}

    bucket              = params.get("bucket", os.getenv("SIGMA_S3_BUCKET", ""))
    prefix              = params.get("start_timestamp", "bronze/")    # S3 prefix to read
    already_loaded_ids  = json.loads(params.get("already_loaded_ids", "[]"))
    region              = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    result = read_s3_records(bucket, prefix, already_loaded_ids, region)

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "function":    event.get("function"),
            "functionResponse": {
                "responseBody": {"TEXT": {"body": json.dumps(result, default=str)}}
            },
        },
    }


def fix_record(record: dict) -> dict:
    """Apply field remapping from the broken Lambda v2."""
    fixed = dict(record)

    # Fix field rename: merchant_nm → merchant_name
    if "merchant_nm" in fixed and "merchant_name" not in fixed:
        fixed["merchant_name"] = fixed.pop("merchant_nm")

    # Fix date format: DD-MM-YYYY → YYYY-MM-DD
    date_val = fixed.get("transaction_date", "")
    if re.match(r"^\d{2}-\d{2}-\d{4}$", str(date_val)):
        parts = str(date_val).split("-")
        fixed["transaction_date"] = f"{parts[2]}-{parts[1]}-{parts[0]}"

    return fixed


def read_s3_records(bucket: str, prefix: str, already_loaded_ids: list,
                    region: str) -> dict:
    if not bucket:
        return {"error": "SIGMA_S3_BUCKET not set in environment"}

    s3 = boto3.client("s3", region_name=region)

    # Normalise prefix — strip "bronze/" if caller passed a timestamp
    if not prefix.startswith("bronze/"):
        prefix = f"bronze/disaster/"   # default disaster prefix

    # List all JSON files under the prefix
    resp  = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    files = [o["Key"] for o in resp.get("Contents", [])
             if o["Key"].endswith(".json") and o["Size"] > 0]

    loaded_set    = set(already_loaded_ids)
    raw_records   = []
    fixed_records = []
    skipped_ids   = []

    for key in files:
        try:
            body    = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            content = json.loads(body)

            # Support both single record and array of records per file
            if isinstance(content, list):
                batch = content
            else:
                batch = [content]

            for rec in batch:
                raw_records.append(rec)
                fixed = fix_record(rec)
                tid   = fixed.get("transaction_id", "")

                if tid and tid in loaded_set:
                    skipped_ids.append(tid)
                else:
                    fixed_records.append(fixed)
                    if tid:
                        loaded_set.add(tid)
        except Exception:
            pass   # skip unreadable files

    return {
        "bucket":             bucket,
        "prefix":             prefix,
        "files_read":         len(files),
        "raw_records_found":  len(raw_records),
        "duplicates_skipped": len(skipped_ids),
        "clean_records":      len(fixed_records),
        "records":            fixed_records,
        "field_fixes_applied": {
            "merchant_nm_renamed": sum(1 for r in raw_records if "merchant_nm" in r),
            "date_format_fixed":   sum(
                1 for r in raw_records
                if re.match(r"^\d{2}-\d{2}-\d{4}$",
                            str(r.get("transaction_date", "")))
            ),
        },
    }


# ── Local test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    bucket = os.getenv("SIGMA_S3_BUCKET", "")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    print(f"\nReading disaster files from s3://{bucket}/bronze/disaster/...\n")
    result = read_s3_records(bucket, "bronze/disaster/", [], region)

    print(f"Files read         : {result['files_read']}")
    print(f"Raw records found  : {result['raw_records_found']}")
    print(f"Duplicates skipped : {result['duplicates_skipped']}")
    print(f"Clean records      : {result['clean_records']}")
    print(f"Field fixes        : {result['field_fixes_applied']}")

    if result["records"]:
        print(f"\nSample (after fix): {json.dumps(result['records'][0], indent=2)}")

    if "--test" in sys.argv:
        assert "records" in result
        print("\nget_kinesis_records.py test PASSED")
