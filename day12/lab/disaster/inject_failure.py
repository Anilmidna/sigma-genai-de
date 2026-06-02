"""
inject_failure.py
Injects the "Silent Disaster" scenario for Day 12.

Run at end of Phase 1, just before Phase 2 begins.

What this does:
  1. Creates sigma-data-producer Lambda with v1 (clean) and v2 (broken)
  2. Switches LIVE alias to v2
  3. Writes 847 malformed JSON records to S3 Bronze under bronze/disaster/
     → Files land in S3 but Snowflake has 0 rows for this window
  4. Students see: S3 has files, Snowflake shows gap. Find why.

Usage:
  python lab/disaster/inject_failure.py
  python lab/disaster/inject_failure.py --dry-run
  python lab/disaster/inject_failure.py --undo
"""

import argparse, boto3, io, json, os, random, sys, time, zipfile
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

REGION   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
BUCKET   = os.getenv("SIGMA_S3_BUCKET", "")
FN_NAME  = os.getenv("PRODUCER_LAMBDA_NAME", "sigma-data-producer")
ALIAS    = os.getenv("PRODUCER_LAMBDA_ALIAS", "LIVE")
ROLE_ARN = os.getenv("LAMBDA_ROLE_ARN", "")

MERCHANTS  = ["QuickMart","FuelPlus","CafeBlend","TechZone","MediPharm",
              "GroceryHub","PetCorner","AutoFix","TravelEasy","ByteStore"]
CATEGORIES = ["retail","fuel","food","electronics","pharmacy",
              "grocery","pet","automotive","travel","tech"]


# ── Lambda code ────────────────────────────────────────────────────────────────

V1_CODE = '''
import boto3, json, os
from datetime import datetime

def handler(event, context):
    s3      = boto3.client("s3")
    bucket  = event.get("bucket", os.environ.get("SIGMA_S3_BUCKET",""))
    records = event.get("records", [])
    key     = f"bronze/clean/{datetime.utcnow().strftime('%Y/%m/%d/%H')}/{event.get('batch_id','batch')}.json"
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(records).encode())
    return {"statusCode": 200, "records_written": len(records), "key": key}
'''.strip()

V2_CODE = '''
import boto3, json, os
from datetime import datetime

def handler(event, context):
    # v2 bug: renames merchant_name → merchant_nm, breaks date format
    s3      = boto3.client("s3")
    bucket  = event.get("bucket", os.environ.get("SIGMA_S3_BUCKET",""))
    records = event.get("records", [])
    broken  = []
    for r in records:
        r["merchant_nm"] = r.pop("merchant_name", r.get("merchant_nm",""))
        d = r.get("transaction_date","")
        if d and len(d) == 10 and d[4] == "-":
            parts = d.split("-")
            r["transaction_date"] = f"{parts[2]}-{parts[1]}-{parts[0]}"
        broken.append(r)
    key = f"bronze/disaster/{datetime.utcnow().strftime('%Y/%m/%d/%H')}/{event.get('batch_id','batch')}.json"
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(broken).encode())
    return {"statusCode": 200, "records_written": len(broken), "key": key}
'''.strip()


def make_record(idx: int) -> dict:
    m = idx % 10
    return {
        "transaction_id":   f"TXN-DISASTER-{idx:05d}",
        "merchant_name":    MERCHANTS[m],
        "category":         CATEGORIES[m],
        "amount":           round(random.uniform(200, 15000), 2),
        "currency":         "INR",
        "transaction_date": "2026-06-04",
        "status":           "completed",
        "customer_id":      f"C{random.randint(1000,1099)}",
        "payment_method":   random.choice(["UPI","card","netbanking"]),
        "merchant_city":    random.choice(["Bengaluru","Mumbai","Chennai","Delhi"]),
    }


def make_zip(code: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("handler.py", code)
    return buf.getvalue()


def ensure_lambda_versions(lam, dry_run: bool):
    if not ROLE_ARN:
        print("  ERROR: LAMBDA_ROLE_ARN not set in lab/.env")
        sys.exit(1)

    exists = True
    try:
        lam.get_function(FunctionName=FN_NAME)
    except lam.exceptions.ResourceNotFoundException:
        exists = False

    if dry_run:
        print(f"  [DRY RUN] Would create {FN_NAME} v1 and v2")
        return

    if not exists:
        lam.create_function(
            FunctionName=FN_NAME, Runtime="python3.12", Role=ROLE_ARN,
            Handler="handler.handler", Code={"ZipFile": make_zip(V1_CODE)},
            Description="Sigma data producer v1 — clean",
            Environment={"Variables": {"SIGMA_S3_BUCKET": BUCKET}},
            Timeout=30,
        )
        lam.get_waiter("function_active").wait(FunctionName=FN_NAME)

    # Deploy v1 code and publish
    lam.update_function_code(FunctionName=FN_NAME, ZipFile=make_zip(V1_CODE))
    lam.get_waiter("function_updated").wait(FunctionName=FN_NAME)
    lam.publish_version(FunctionName=FN_NAME, Description="v1 clean producer")
    print("  v1 (clean) published.")

    # Deploy v2 code and publish
    lam.update_function_code(FunctionName=FN_NAME, ZipFile=make_zip(V2_CODE))
    lam.get_waiter("function_updated").wait(FunctionName=FN_NAME)
    lam.publish_version(FunctionName=FN_NAME, Description="v2 broken — merchant_nm + DD-MM-YYYY")
    print("  v2 (broken) published.")


def set_alias_to_v2(lam, dry_run: bool):
    if dry_run:
        print("  [DRY RUN] Would switch LIVE alias to v2")
        return

    versions = lam.list_versions_by_function(FunctionName=FN_NAME)["Versions"]
    numbered = sorted([v for v in versions if v["Version"] != "$LATEST"],
                      key=lambda x: int(x["Version"]))
    v2_num = numbered[-1]["Version"] if numbered else "2"

    try:
        lam.get_alias(FunctionName=FN_NAME, Name=ALIAS)
        lam.update_alias(FunctionName=FN_NAME, Name=ALIAS, FunctionVersion=v2_num,
                         Description="v2 broken — injected for Day 12")
    except lam.exceptions.ResourceNotFoundException:
        lam.create_alias(FunctionName=FN_NAME, Name=ALIAS, FunctionVersion=v2_num,
                         Description="v2 broken — injected for Day 12")
    print(f"  LIVE alias → v{v2_num} (broken)")


def write_disaster_files(s3, n_records: int, dry_run: bool):
    if dry_run:
        print(f"  [DRY RUN] Would write {n_records} malformed records to S3")
        return

    if not BUCKET:
        print("  ERROR: SIGMA_S3_BUCKET not set in lab/.env")
        sys.exit(1)

    records = [make_record(i) for i in range(n_records)]

    # Apply v2 transformation (what the broken Lambda would do)
    broken = []
    for r in records:
        r2 = dict(r)
        r2["merchant_nm"] = r2.pop("merchant_name")
        d = r2["transaction_date"]
        parts = d.split("-")
        r2["transaction_date"] = f"{parts[2]}-{parts[1]}-{parts[0]}"
        broken.append(r2)

    # Write in batches of 50 records per file
    batch_size = 50
    files_written = 0
    prefix = "bronze/disaster/2026/06/04/02/"

    for i in range(0, len(broken), batch_size):
        batch = broken[i:i + batch_size]
        key   = f"{prefix}batch_{i//batch_size:03d}.json"
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(batch).encode(),
            ContentType="application/json",
        )
        files_written += 1

    print(f"  {n_records} malformed records → {files_written} files in s3://{BUCKET}/{prefix}")
    print(f"  Field: merchant_nm (not merchant_name)")
    print(f"  Date:  DD-MM-YYYY (not YYYY-MM-DD)")
    print(f"  These files will NOT load to Snowflake — that is the disaster.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--undo",    action="store_true")
    parser.add_argument("--records", type=int, default=847)
    args = parser.parse_args()

    lam = boto3.client("lambda", region_name=REGION)
    s3  = boto3.client("s3",     region_name=REGION)

    print("=" * 65)
    print("SIGMA DATATECH — SILENT DISASTER INJECTION")
    print("=" * 65)
    print(f"  Mode   : {'DRY RUN' if args.dry_run else ('UNDO' if args.undo else 'INJECT')}")
    print(f"  Bucket : {BUCKET}")
    print(f"  Records: {args.records}")
    print("=" * 65)

    if args.undo:
        print("\nUNDO: Rolling LIVE alias back to v1...")
        try:
            versions = lam.list_versions_by_function(FunctionName=FN_NAME)["Versions"]
            numbered = sorted([v for v in versions if v["Version"] != "$LATEST"],
                              key=lambda x: int(x["Version"]))
            v1 = numbered[0]["Version"] if numbered else "1"
            lam.update_alias(FunctionName=FN_NAME, Name=ALIAS, FunctionVersion=v1)
            print(f"  LIVE alias → v{v1} (clean)")
        except Exception as e:
            print(f"  ERROR: {e}")
        return

    print("\n[1/3] Setting up Lambda versions...")
    ensure_lambda_versions(lam, args.dry_run)

    print("\n[2/3] Switching LIVE alias to v2 (broken)...")
    set_alias_to_v2(lam, args.dry_run)

    print(f"\n[3/3] Writing {args.records} malformed records to S3...")
    write_disaster_files(s3, args.records, args.dry_run)

    print("\n" + "=" * 65)
    print("Disaster injected.")
    print(f"  S3 has {args.records} files in bronze/disaster/ — visible to students")
    print(f"  Snowflake has 0 rows for this window — the gap students investigate")
    print(f"  Lambda LIVE alias = v2 (broken) — Rollback Agent fixes this")
    print()
    print("  To undo: python lab/disaster/inject_failure.py --undo")
    print("=" * 65)


if __name__ == "__main__":
    main()
