"""
==============================================================================
DAY 13 — AGENT 1: SCHEMA EVOLUTION AGENT
==============================================================================
Detects schema changes in the latest S3 Bronze file compared to the known
Silver table schema. Uses Bedrock to generate remediation SQL and a mapping
plan. Saves an incident report.

Usage:
  python agents/schema_evolution_agent.py \
    --bucket sigma-datatech-anil \
    --prefix bronze/transactions/ \
    --baseline-table sigma.silver.transactions \
    --region us-east-1

Output:
  agent_outputs/schema_drift_incident_<timestamp>.json
==============================================================================
"""

import argparse, boto3, gzip, json, os, sys
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import pandas as pd
except ImportError:
    print("[ERROR] pip install pandas")
    sys.exit(1)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "agent_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MODEL_ID = "amazon.nova-pro-v1:0"

def call_bedrock(prompt, region="us-east-1", max_tokens=1000):
    client = boto3.client("bedrock-runtime", region_name=region)
    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.1},
    }
    resp = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    return json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"].strip()

def get_latest_s3_file(s3_client, bucket, prefix):
    """Get the most recently modified object under prefix."""
    resp = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    objects = resp.get("Contents", [])
    if not objects:
        return None
    latest = sorted(objects, key=lambda x: x["LastModified"], reverse=True)[0]
    return latest["Key"]

def read_s3_json_gz(s3_client, bucket, key):
    """Read a gzipped NDJSON file from S3 and return as DataFrame."""
    obj  = s3_client.get_object(Bucket=bucket, Key=key)
    data = gzip.decompress(obj["Body"].read()).decode("utf-8")
    rows = [json.loads(line) for line in data.strip().splitlines() if line.strip()]
    return pd.DataFrame(rows)

def get_baseline_schema(baseline_table):
    """
    In production this would query Databricks/Snowflake.
    For the lab we define the known clean schema.
    """
    return {
        "transaction_id":   "STRING",
        "merchant_name":    "STRING",
        "category":         "STRING",
        "amount":           "DOUBLE",
        "currency":         "STRING",
        "transaction_date": "DATE",
        "status":           "STRING",
        "customer_id":      "STRING",
        "payment_method":   "STRING",
        "merchant_city":    "STRING",
    }

def detect_drift(baseline_schema, new_columns):
    """Compare baseline schema to new columns found in S3 file."""
    baseline_cols = set(baseline_schema.keys())
    new_cols      = set(new_columns)

    added   = new_cols - baseline_cols
    removed = baseline_cols - new_cols

    # Detect renames: common heuristic — check for abbreviated versions
    rename_map = {}
    for old in list(removed):
        for new in list(added):
            if old[:4].lower() == new[:4].lower():   # first 4 chars match
                rename_map[new] = old
                added.discard(new)
                removed.discard(old)

    return {
        "added":   list(added),
        "removed": list(removed),
        "renamed": rename_map,
        "has_drift": bool(added or removed or rename_map),
    }

def main():
    parser = argparse.ArgumentParser(description="Schema Evolution Agent")
    parser.add_argument("--bucket",          required=True)
    parser.add_argument("--prefix",          required=True)
    parser.add_argument("--baseline-table",  default="sigma.silver.transactions")
    parser.add_argument("--region",          default="us-east-1")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("SCHEMA EVOLUTION AGENT")
    print("="*60)

    s3     = boto3.client("s3", region_name=args.region)
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Step 1: Get latest S3 file
    print(f"\n  Scanning S3: s3://{args.bucket}/{args.prefix}")
    latest_key = get_latest_s3_file(s3, args.bucket, args.prefix)
    if not latest_key:
        print("  [WARN] No files found in S3 prefix. Has Firehose delivered yet?")
        print("         Wait 60-90 seconds after running data_generator.py")
        sys.exit(0)
    print(f"  Latest file: {latest_key}")

    # Step 2: Read file and get columns
    try:
        df         = read_s3_json_gz(s3, args.bucket, latest_key)
        new_cols   = list(df.columns)
        print(f"  Columns in file: {new_cols}")
    except Exception as e:
        print(f"  [ERROR] Could not read file: {e}")
        sys.exit(1)

    # Step 3: Get baseline schema
    baseline = get_baseline_schema(args.baseline_table)
    print(f"  Baseline schema ({args.baseline_table}): {list(baseline.keys())}")

    # Step 4: Detect drift
    drift = detect_drift(baseline, new_cols)

    if not drift["has_drift"]:
        print("\n  ✓ No schema drift detected. Pipeline is clean.")
        report = {
            "agent": "SchemaEvolutionAgent",
            "timestamp": datetime.now().isoformat(),
            "baseline_table": args.baseline_table,
            "latest_file": latest_key,
            "drift_detected": False,
            "student_judgment": "NOT ANSWERED",
        }
        path = os.path.join(OUTPUT_DIR, f"schema_drift_incident_{ts}.json")
        with open(path, "w") as f: json.dump(report, f, indent=2)
        print(f"  Report saved: {path}")
        return

    # Step 5: Drift detected — call Bedrock for remediation
    print("\n  DRIFT DETECTED:")
    if drift["added"]:
        for c in drift["added"]:
            print(f"    + {c} (new column)")
    if drift["removed"]:
        for c in drift["removed"]:
            print(f"    - {c} (removed)")
    if drift["renamed"]:
        for new, old in drift["renamed"].items():
            print(f"    ~ {old} → {new} (renamed)")

    print("\n  Calling Bedrock Nova Pro for remediation plan...")

    prompt = f"""You are a senior data engineer at Sigma DataTech (Indian fintech).

A schema drift was detected in the Kinesis → S3 → Databricks pipeline.

Baseline table: {args.baseline_table}
Baseline columns: {list(baseline.keys())}

New columns in latest S3 file: {new_cols}

Drift analysis:
- New columns added: {drift['added']}
- Columns removed: {drift['removed']}
- Columns renamed: {drift['renamed']}

Generate a remediation plan in JSON:
{{
  "alter_statements": ["ALTER TABLE ... ADD COLUMN ..."],
  "column_mapping": {{"new_name": "old_name"}},
  "transform_code": "python/pyspark snippet to handle the rename in Silver transform",
  "risk_level": "low/medium/high",
  "risk_reason": "one sentence",
  "recommended_action": "one sentence"
}}
Return JSON only."""

    response = call_bedrock(prompt, args.region)
    try:
        start = response.index("{")
        end   = response.rindex("}") + 1
        remediation = json.loads(response[start:end])
    except Exception:
        remediation = {
            "alter_statements": [f"ALTER TABLE {args.baseline_table} ADD COLUMN {c} STRING;" for c in drift["added"]],
            "column_mapping":   {new: old for new, old in drift["renamed"].items()},
            "transform_code":   "df = df.withColumn('merchant_name', coalesce(col('merchant_name'), col('merchant_nm')))",
            "risk_level":       "medium",
            "risk_reason":      "Renamed column will break downstream transforms that reference old name",
            "recommended_action": "Apply ALTER statements and update Silver transform before next load",
        }

    print("\n  Remediation plan:")
    for stmt in remediation.get("alter_statements", []):
        print(f"    SQL: {stmt}")
    if remediation.get("column_mapping"):
        print(f"    Mapping: {remediation['column_mapping']}")
    print(f"    Risk: {remediation.get('risk_level','?').upper()} — {remediation.get('risk_reason','')}")
    print(f"    Action: {remediation.get('recommended_action','')}")

    # Judgment question
    print("\n" + "="*60)
    print("JUDGMENT QUESTION")
    print("="*60)
    print("""
  The agent added a nullable column automatically. Downstream analysts
  use merchant_name in their Snowflake reports. The rename to merchant_nm
  means their reports now show NULL for merchant_name.

  What single guardrail would you add to this agent before running it in prod?
""")
    judgment = input("  Your answer (1 sentence): ").strip() or "NOT ANSWERED"

    # Save report
    report = {
        "agent":            "SchemaEvolutionAgent",
        "timestamp":        datetime.now().isoformat(),
        "baseline_table":   args.baseline_table,
        "latest_file":      latest_key,
        "drift_detected":   True,
        "drift_details":    drift,
        "remediation":      remediation,
        "student_judgment": judgment,
    }
    path = os.path.join(OUTPUT_DIR, f"schema_drift_incident_{ts}.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  ✓ Incident report saved: {path}")
    print("  Pipeline can resume with the mapping applied.")
    print("="*60)

if __name__ == "__main__":
    main()
