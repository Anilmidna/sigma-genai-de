"""
Downloads the latest incident report from S3 and prints it.
Run after the supervisor agent completes.
"""

import boto3, os, sys
from dotenv import load_dotenv
load_dotenv()

bucket = os.getenv("SIGMA_S3_BUCKET", "")
region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

if not bucket:
    print("Set SIGMA_S3_BUCKET in .env"); sys.exit(1)

s3   = boto3.client("s3", region_name=region)
resp = s3.list_objects_v2(Bucket=bucket, Prefix="reports/")
objs = [o for o in resp.get("Contents", []) if o["Key"].endswith(".md")]

if not objs:
    print(f"No reports found in s3://{bucket}/reports/")
    print("Run pipeline_trigger.py first.")
    sys.exit(1)

latest = sorted(objs, key=lambda x: x["LastModified"], reverse=True)[0]
print(f"Latest report: s3://{bucket}/{latest['Key']}")
print(f"Size: {latest['Size']:,} bytes | Modified: {latest['LastModified']}\n")
print("=" * 70)

content = s3.get_object(Bucket=bucket, Key=latest["Key"])["Body"].read().decode("utf-8")
print(content)
print("=" * 70)
print(f"\nFull path: s3://{bucket}/{latest['Key']}")
