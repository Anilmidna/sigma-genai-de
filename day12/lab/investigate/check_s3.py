"""
Phase 2 Investigation Tool — S3 Bronze
Lists files in S3 Bronze by hour. This is the key evidence:
files exist in S3 but Snowflake shows 0 rows for the same window.
The gap between S3 and Snowflake IS the problem.
"""

import boto3, json, os, sys
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

bucket = os.getenv("SIGMA_S3_BUCKET", "")
region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

if not bucket or "YOURTEAM" in bucket:
    print("[ERROR] Set SIGMA_S3_BUCKET in lab/.env")
    sys.exit(1)

s3  = boto3.client("s3", region_name=region)

print(f"\nS3 BRONZE — Files in {bucket}/bronze/")
print("=" * 65)

# List all files in bronze/
resp  = s3.list_objects_v2(Bucket=bucket, Prefix="bronze/")
files = resp.get("Contents", [])

if not files:
    print("\n  No files found in bronze/. Run data_generator.py first.")
    sys.exit(0)

# Group by prefix (date/hour folder)
from collections import defaultdict
by_prefix = defaultdict(list)
for obj in files:
    key  = obj["Key"]
    # Group by the folder path
    parts = key.split("/")
    if len(parts) >= 2:
        folder = "/".join(parts[:-1])
    else:
        folder = "bronze"
    by_prefix[folder].append(obj)

print(f"\n  {'Folder':<45} {'Files':>6} {'Total Size':>12}")
print("  " + "-" * 65)
total_files = 0
total_bytes = 0
for folder in sorted(by_prefix.keys()):
    objs  = by_prefix[folder]
    count = len(objs)
    size  = sum(o["Size"] for o in objs)
    total_files += count
    total_bytes += size

    # Flag disaster files
    flag = "  ← DISASTER FILES" if "disaster" in folder else ""
    print(f"  {folder:<45} {count:>6} {size:>12,} bytes{flag}")

print("  " + "-" * 65)
print(f"  {'TOTAL':<45} {total_files:>6} {total_bytes:>12,} bytes")

# Show a sample record from the disaster folder to reveal malformed content
disaster_files = [o for o in files if "disaster" in o["Key"] and o["Size"] > 0]
if disaster_files:
    sample_key = disaster_files[0]["Key"]
    print(f"\n  Downloading sample record from disaster folder...")
    print(f"  File: {sample_key}")
    try:
        body    = s3.get_object(Bucket=bucket, Key=sample_key)["Body"].read()
        content = json.loads(body)
        if isinstance(content, list) and content:
            content = content[0]
        print(f"\n  SAMPLE RECORD:")
        for k, v in content.items():
            flag = "  ← WRONG FIELD NAME" if k == "merchant_nm" else ""
            flag = "  ← WRONG DATE FORMAT" if k == "transaction_date" and "-" in str(v) and str(v)[2] == "-" else flag
            print(f"    {k}: {v}{flag}")
        print()
        print("  KEY QUESTION: Compare these field names to check_snowflake.py output.")
        print("  Is merchant_nm or merchant_name in the Snowflake column definition?")
        print("  What happens when Snowflake COPY INTO sees merchant_nm instead?")
    except Exception as e:
        print(f"  Could not read sample: {e}")
else:
    print("\n  No disaster files found. Run inject_failure.py first.")

print()
