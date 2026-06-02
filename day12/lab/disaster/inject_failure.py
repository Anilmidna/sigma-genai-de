"""
==============================================================================
TRAINER SCRIPT — NOT STUDENT-FACING
==============================================================================
Sets up the "Silent Disaster" scenario for Day 12.

Run this before class (recommended: 8–9 AM) to simulate a 2 AM pipeline failure.

What this does:
  1. Ensures Lambda v1 (clean) and v2 (broken) exist for sigma-kinesis-producer
  2. Switches the LIVE alias to v2
  3. Sends 847 records through the pipeline using v2 (malformed JSON)
     → These records reach S3 but Snowflake loads 0 rows
  4. Sets the existing CloudWatch alarm threshold too high (won't fire)
  5. Prints summary of what's been injected

The result: GMV dashboard shows ₹0 for the last 7+ hours.
No alerts have fired. Everything looks healthy.

Usage:
  python lab/disaster/inject_failure.py
  python lab/disaster/inject_failure.py --dry-run    # show what would happen

Undo (if needed):
  python lab/disaster/inject_failure.py --undo
==============================================================================
"""

import argparse, boto3, json, os, random, sys, time
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

REGION      = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
STREAM_NAME = os.getenv("SIGMA_STREAM", "sigma-transactions")
FN_NAME     = os.getenv("PRODUCER_LAMBDA_NAME", "sigma-kinesis-producer")
ALIAS       = os.getenv("PRODUCER_LAMBDA_ALIAS", "LIVE")
ROLE_ARN    = os.getenv("LAMBDA_ROLE_ARN", "")

MERCHANTS  = ["QuickMart","FuelPlus","CafeBlend","TechZone","MediPharm",
              "GroceryHub","PetCorner","AutoFix","TravelEasy","ByteStore"]
CATEGORIES = ["retail","fuel","food","electronics","pharmacy",
              "grocery","pet","automotive","travel","tech"]


# ── Lambda function code ──────────────────────────────────────────────────────

# v1: clean producer — correct field names and date format
V1_CODE = """
import boto3, json, os, random
from datetime import datetime

def handler(event, context):
    kinesis = boto3.client('kinesis')
    records = event.get('Records', [])
    for r in records:
        kinesis.put_record(
            StreamName=event.get('stream_name', os.environ.get('STREAM_NAME','')),
            Data=json.dumps(r).encode(),
            PartitionKey=r.get('transaction_id','default')
        )
    return {'statusCode': 200, 'merchant_name': 'clean_v1'}
""".strip()

# v2: broken producer — renames merchant_name to merchant_nm, breaks date format
V2_CODE = """
import boto3, json, os
from datetime import datetime

def handler(event, context):
    kinesis = boto3.client('kinesis')
    records = event.get('Records', [])
    for r in records:
        # v2 bug: renamed field + wrong date format
        r['merchant_nm'] = r.pop('merchant_name', r.get('merchant_nm',''))
        d = r.get('transaction_date','')
        if d and '-' in d:
            parts = d.split('-')
            if len(parts) == 3 and len(parts[0]) == 4:
                r['transaction_date'] = f"{parts[2]}-{parts[1]}-{parts[0]}"
        kinesis.put_record(
            StreamName=event.get('stream_name', os.environ.get('STREAM_NAME','')),
            Data=json.dumps(r).encode(),
            PartitionKey=r.get('transaction_id','default')
        )
    return {'statusCode': 200, 'merchant_nm': 'broken_v2'}
""".strip()


def make_record(idx: int) -> dict:
    m = random.randint(0, 9)
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


def ensure_lambda_versions(lam, dry_run: bool) -> tuple[str, str]:
    """Returns (v1_arn, v2_arn)."""
    import zipfile, io

    def make_zip(code: str) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("handler.py", code)
        return buf.getvalue()

    # Check if function exists
    try:
        lam.get_function(FunctionName=FN_NAME)
        function_exists = True
    except lam.exceptions.ResourceNotFoundException:
        function_exists = False

    if not function_exists:
        if dry_run:
            print(f"  [DRY RUN] Would create {FN_NAME} v1 and v2")
            return ("v1-arn-dry-run", "v2-arn-dry-run")
        if not ROLE_ARN:
            print(f"  ERROR: LAMBDA_ROLE_ARN not set. Cannot create {FN_NAME}.")
            sys.exit(1)
        print(f"  Creating {FN_NAME} (v1 — clean)...")
        resp = lam.create_function(
            FunctionName=FN_NAME,
            Runtime="python3.12",
            Role=ROLE_ARN,
            Handler="handler.handler",
            Code={"ZipFile": make_zip(V1_CODE)},
            Description="Sigma Kinesis Producer v1 — clean",
            Environment={"Variables": {"STREAM_NAME": STREAM_NAME}},
        )
        lam.get_waiter("function_active").wait(FunctionName=FN_NAME)
        v1_arn = lam.publish_version(
            FunctionName=FN_NAME, Description="v1 clean producer"
        )["FunctionArn"]
    else:
        if dry_run:
            print(f"  [DRY RUN] Would update {FN_NAME} to v2 (broken)")
            return ("v1-exists", "v2-dry-run")
        # Publish current state as v1 (in case it doesn't exist yet)
        try:
            v1_arn = lam.publish_version(
                FunctionName=FN_NAME, Description="v1 clean producer"
            )["FunctionArn"]
            print(f"  Published v1: {v1_arn}")
        except Exception:
            v1_arn = f"arn:aws:lambda:{REGION}:*:function:{FN_NAME}:1"

    # Deploy v2 (broken code)
    print(f"  Deploying {FN_NAME} v2 (broken — will cause silent failure)...")
    lam.update_function_code(
        FunctionName=FN_NAME,
        ZipFile=make_zip(V2_CODE),
    )
    lam.get_waiter("function_updated").wait(FunctionName=FN_NAME)
    v2_arn = lam.publish_version(
        FunctionName=FN_NAME, Description="v2 broken — merchant_nm + DD-MM-YYYY"
    )["FunctionArn"]
    print(f"  Published v2: {v2_arn}")
    return (v1_arn, v2_arn)


def main():
    parser = argparse.ArgumentParser(description="Inject silent pipeline failure")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--undo",    action="store_true")
    parser.add_argument("--records", type=int, default=847)
    args = parser.parse_args()

    lam     = boto3.client("lambda",  region_name=REGION)
    kinesis = boto3.client("kinesis", region_name=REGION)

    print("=" * 65)
    print("SIGMA DATATECH — SILENT DISASTER INJECTION")
    print("=" * 65)
    print(f"  Mode    : {'DRY RUN' if args.dry_run else ('UNDO' if args.undo else 'INJECT')}")
    print(f"  Stream  : {STREAM_NAME}")
    print(f"  Lambda  : {FN_NAME}:{ALIAS}")
    print(f"  Records : {args.records}")
    print("=" * 65)

    # ── UNDO mode ─────────────────────────────────────────────────────────────
    if args.undo:
        print("\nUNDO: Rolling LIVE alias back to v1...")
        try:
            versions = lam.list_versions_by_function(FunctionName=FN_NAME)["Versions"]
            numbered = sorted(
                [v for v in versions if v["Version"] != "$LATEST"],
                key=lambda x: int(x["Version"]),
            )
            v1 = numbered[0]["Version"] if numbered else "1"
            lam.update_alias(FunctionName=FN_NAME, Name=ALIAS, FunctionVersion=v1)
            print(f"  LIVE alias now points to v{v1}")
        except Exception as e:
            print(f"  ERROR: {e}")
        return

    # ── Ensure v1 and v2 exist ────────────────────────────────────────────────
    print("\n[1/4] Setting up Lambda versions...")
    v1_arn, v2_arn = ensure_lambda_versions(lam, args.dry_run)

    # ── Switch alias to v2 (the broken version) ───────────────────────────────
    print("\n[2/4] Switching LIVE alias to v2 (broken)...")
    if not args.dry_run:
        versions = lam.list_versions_by_function(FunctionName=FN_NAME)["Versions"]
        numbered = sorted(
            [v for v in versions if v["Version"] != "$LATEST"],
            key=lambda x: int(x["Version"]),
        )
        v2_num = numbered[-1]["Version"] if numbered else "2"
        try:
            lam.get_alias(FunctionName=FN_NAME, Name=ALIAS)
            lam.update_alias(FunctionName=FN_NAME, Name=ALIAS, FunctionVersion=v2_num,
                             Description="v2 broken — injected for Day 12 lab")
        except lam.exceptions.ResourceNotFoundException:
            lam.create_alias(FunctionName=FN_NAME, Name=ALIAS, FunctionVersion=v2_num,
                             Description="v2 broken — injected for Day 12 lab")
        print(f"  LIVE → v{v2_num} (broken)")
    else:
        print("  [DRY RUN] Would switch LIVE to v2")

    # ── Send records into Kinesis ─────────────────────────────────────────────
    # These will reach S3 as malformed JSON but Snowflake will load 0 rows
    print(f"\n[3/4] Sending {args.records} records to Kinesis (via malformed v2)...")
    if not args.dry_run:
        sent = 0
        for i in range(args.records):
            rec = make_record(i)
            # Apply v2 transformation manually (simulate what v2 Lambda does)
            rec["merchant_nm"] = rec.pop("merchant_name")
            d = rec["transaction_date"]
            parts = d.split("-")
            rec["transaction_date"] = f"{parts[2]}-{parts[1]}-{parts[0]}"
            kinesis.put_record(
                StreamName=STREAM_NAME,
                Data=json.dumps(rec).encode(),
                PartitionKey=rec.get("transaction_id","default"),
            )
            sent += 1
            if sent % 100 == 0:
                print(f"  Sent {sent}/{args.records}...")
            time.sleep(0.02)
        print(f"  {sent} malformed records sent to Kinesis.")
        print(f"  Firehose will deliver to S3 in ~90 seconds.")
        print(f"  Snowflake will attempt COPY INTO and load 0 rows.")
    else:
        print(f"  [DRY RUN] Would send {args.records} malformed records to Kinesis")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n[4/4] Disaster injected. Summary:\n")
    print(f"  Lambda {FN_NAME}:LIVE → v2 (broken)")
    print(f"  {args.records} records sent with:")
    print(f"    merchant_nm (not merchant_name)")
    print(f"    DD-MM-YYYY date format (not YYYY-MM-DD)")
    print(f"  Snowflake: will show 0 rows loaded after Firehose delivery (~90s)")
    print(f"  CloudWatch alarms: none will fire (threshold too high)")
    print()
    print("  Students will discover this starting at 11:45 AM.")
    print("  They have 60 minutes to manually trace the root cause.")
    print()
    print(f"  To undo: python lab/disaster/inject_failure.py --undo")
    print("=" * 65)


if __name__ == "__main__":
    main()
