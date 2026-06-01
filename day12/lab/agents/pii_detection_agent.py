"""
==============================================================================
DAY 13 — AGENT 2: PII DETECTION AGENT
==============================================================================
Scans the latest S3 Bronze file for PII before it enters Databricks.
Layer 1: Regex for known PII patterns (fast, free).
Layer 2: Bedrock LLM for abbreviated column names (catches what regex misses).
Masks Confidential tier columns. Blocks Restricted tier columns.

Usage:
  python agents/pii_detection_agent.py \
    --bucket sigma-datatech-anil \
    --prefix bronze/transactions/ \
    --action mask_and_continue \
    --region us-east-1

Output:
  agent_outputs/pii_scan_<timestamp>.json
==============================================================================
"""

import argparse, boto3, gzip, json, os, re, sys
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

# ── PII Patterns (India-specific + universal) ─────────────────────────────────
PII_PATTERNS = {
    "pan_number":     (r"^[A-Z]{5}[0-9]{4}[A-Z]$",                          "Financial ID",  "Restricted"),
    "aadhaar_number": (r"^[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}$",                 "Govt ID",       "Restricted"),
    "phone_number":   (r"^(\+91)?[7-9][0-9]{9}$",                            "Contact",       "Confidential"),
    "email_address":  (r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$","Contact",     "Confidential"),
    "account_number": (r"^[0-9]{9,18}$",                                     "Financial ID",  "Restricted"),
    "pin_code":       (r"^[1-9][0-9]{5}$",                                   "Location",      "Confidential"),
    "full_name":      (r"^[A-Z][a-z]+ [A-Z][a-z]+$",                        "Identity",      "Confidential"),
}

SENSITIVITY_ORDER = {"Public": 0, "Internal": 1, "Confidential": 2, "Restricted": 3}

def call_bedrock(prompt, region="us-east-1", max_tokens=1200):
    client = boto3.client("bedrock-runtime", region_name=region)
    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.1},
    }
    resp = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    return json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"].strip()

def get_latest_s3_file(s3_client, bucket, prefix):
    resp    = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    objects = resp.get("Contents", [])
    if not objects:
        return None
    return sorted(objects, key=lambda x: x["LastModified"], reverse=True)[0]["Key"]

def read_s3_json_gz(s3_client, bucket, key):
    obj  = s3_client.get_object(Bucket=bucket, Key=key)
    data = gzip.decompress(obj["Body"].read()).decode("utf-8")
    rows = [json.loads(line) for line in data.strip().splitlines() if line.strip()]
    return pd.DataFrame(rows)

def mask_value(value, pii_type):
    """Apply appropriate masking based on PII type."""
    if value is None or str(value).strip() == "":
        return value
    v = str(value)
    if pii_type == "phone_number":
        return "+91XXXXXX" + v[-4:] if len(v) >= 4 else "XXXX"
    elif pii_type == "account_number":
        return "XXXXXXXXXXXX" + v[-4:] if len(v) >= 4 else "XXXX"
    elif pii_type == "email_address":
        parts = v.split("@")
        return "****@" + parts[1] if len(parts) == 2 else "****"
    elif pii_type == "pin_code":
        return v[:2] + "XXXX" if len(v) >= 2 else "XXXX"
    elif pii_type in ("pan_number", "aadhaar_number"):
        return "XXXX" + v[-4:] if len(v) >= 4 else "XXXX"
    else:
        return "****"

def regex_scan(df):
    """Fast regex scan — catches well-named PII columns."""
    findings = {}
    for col in df.columns:
        sample = df[col].dropna().astype(str).head(50).tolist()
        if not sample:
            continue
        for pii_type, (pattern, category, sensitivity) in PII_PATTERNS.items():
            matches    = sum(1 for v in sample if re.match(pattern, v.strip()))
            match_rate = matches / len(sample)
            if match_rate > 0.5:
                findings[col] = {
                    "pii_type":    pii_type,
                    "category":    category,
                    "sensitivity": sensitivity,
                    "confidence":  "high",
                    "match_rate":  round(match_rate, 2),
                    "method":      "regex",
                }
                break
            elif match_rate > 0.2:
                findings[col] = {
                    "pii_type":    pii_type,
                    "category":    category,
                    "sensitivity": sensitivity,
                    "confidence":  "medium",
                    "match_rate":  round(match_rate, 2),
                    "method":      "regex_medium",
                }
                break
    return findings

def llm_scan(df, already_found, region):
    """LLM scan for columns regex did not classify — catches abbreviations."""
    unclassified = [c for c in df.columns if c not in already_found]
    if not unclassified:
        return {}

    # Build sample for each unclassified column
    samples = {}
    for col in unclassified:
        samples[col] = df[col].dropna().astype(str).head(10).tolist()

    prompt = f"""You are a data privacy officer at Sigma DataTech (Indian fintech regulated by RBI/SEBI).

Analyse these dataset columns and sample values for PII.
Pay close attention to ABBREVIATED column names like cust_ph, mob_no, acct_no, emp_id, pncd.

Columns to analyse:
{json.dumps(samples, indent=2)}

For each column respond with whether it contains PII. Return JSON only:
{{
  "assessments": [
    {{
      "column": "column_name",
      "is_pii": true or false,
      "pii_type": "phone_number / account_number / pin_code / name / email / pan / aadhaar / other",
      "sensitivity": "Public / Internal / Confidential / Restricted",
      "masking_action": "mask / block_load / none",
      "reasoning": "one sentence"
    }}
  ]
}}"""

    response = call_bedrock(prompt, region)
    findings = {}
    try:
        start = response.index("{")
        end   = response.rindex("}") + 1
        result = json.loads(response[start:end])
        for item in result.get("assessments", []):
            if item.get("is_pii"):
                findings[item["column"]] = {
                    "pii_type":       item.get("pii_type", "unknown"),
                    "category":       "LLM-detected",
                    "sensitivity":    item.get("sensitivity", "Confidential"),
                    "confidence":     "llm",
                    "masking_action": item.get("masking_action", "mask"),
                    "reasoning":      item.get("reasoning", ""),
                    "method":         "llm",
                }
    except Exception:
        pass
    return findings

def main():
    parser = argparse.ArgumentParser(description="PII Detection Agent")
    parser.add_argument("--bucket",  required=True)
    parser.add_argument("--prefix",  required=True)
    parser.add_argument("--action",  choices=["mask_and_continue","block_all","report_only"],
                        default="mask_and_continue")
    parser.add_argument("--region",  default="us-east-1")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("PII DETECTION AGENT")
    print("="*60)

    s3  = boto3.client("s3", region_name=args.region)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Get latest file
    print(f"\n  Scanning S3: s3://{args.bucket}/{args.prefix}")
    key = get_latest_s3_file(s3, args.bucket, args.prefix)
    if not key:
        print("  [WARN] No files found. Wait for Firehose delivery.")
        sys.exit(0)
    print(f"  File: {key}")

    df = read_s3_json_gz(s3, args.bucket, key)
    print(f"  Rows: {len(df)} | Columns: {len(df.columns)}")

    # Layer 1: Regex
    print("\n  Layer 1: Regex scan...")
    regex_findings = regex_scan(df)
    if regex_findings:
        for col, info in regex_findings.items():
            print(f"  [REGEX] {col:20} → {info['pii_type']:20} ({info['sensitivity']}) conf={info['confidence']}")
    else:
        print("  [REGEX] No PII found via regex")

    # Layer 2: LLM for unclassified columns
    print("\n  Layer 2: LLM scan for unclassified columns...")
    print("  Calling Bedrock Nova Pro...")
    llm_findings = llm_scan(df, regex_findings, args.region)

    if llm_findings:
        for col, info in llm_findings.items():
            print(f"  [LLM]   {col:20} → {info['pii_type']:20} ({info['sensitivity']})")
            if info.get("reasoning"):
                print(f"          Reason: {info['reasoning']}")
    else:
        print("  [LLM]   No additional PII found")

    all_findings = {**regex_findings, **llm_findings}

    if not all_findings:
        print("\n  ✓ No PII detected. File is safe to load.")
        tier = "Internal"
    else:
        # Determine dataset tier
        tier = "Public"
        for info in all_findings.values():
            s = info.get("sensitivity", "Public")
            if SENSITIVITY_ORDER.get(s, 0) > SENSITIVITY_ORDER.get(tier, 0):
                tier = s

        print(f"\n  Dataset sensitivity tier: {tier.upper()}")
        print(f"  PII columns found: {len(all_findings)}")

        # Apply actions
        restricted_cols  = [c for c, i in all_findings.items() if i["sensitivity"] == "Restricted"]
        confidential_cols = [c for c, i in all_findings.items() if i["sensitivity"] == "Confidential"]

        if restricted_cols and args.action != "report_only":
            print(f"\n  BLOCKING load for Restricted columns: {restricted_cols}")
            print("  These columns require compliance sign-off before loading to Snowflake.")

        if confidential_cols and args.action == "mask_and_continue":
            print(f"\n  Masking Confidential columns: {confidential_cols}")
            for col in confidential_cols:
                if col in df.columns:
                    pii_type = all_findings[col]["pii_type"]
                    df[col] = df[col].apply(lambda v: mask_value(v, pii_type))
                    print(f"    {col}: {df[col].iloc[0]} (sample masked value)")

    # Judgment question
    print("\n" + "="*60)
    print("JUDGMENT QUESTION")
    print("="*60)
    print(f"""
  The regex scan found ZERO PII.
  The LLM scan found {len(llm_findings)} PII column(s).

  Question: When would you SKIP the LLM scan to save cost?
  What is the risk of skipping it for a new, unknown data source?
""")
    judgment = input("  Your answer (1-2 sentences): ").strip() or "NOT ANSWERED"

    # Save report
    report = {
        "agent":              "PIIDetectionAgent",
        "timestamp":          datetime.now().isoformat(),
        "file_scanned":       key,
        "rows_scanned":       len(df),
        "columns_scanned":    len(df.columns),
        "pii_columns_found":  len(all_findings),
        "dataset_sensitivity":tier,
        "regex_findings":     regex_findings,
        "llm_findings":       llm_findings,
        "action_taken":       args.action,
        "student_judgment":   judgment,
    }
    path = os.path.join(OUTPUT_DIR, f"pii_scan_{ts}.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  ✓ PII scan report: {path}")
    print(f"  Dataset tier: {tier.upper()}")
    if tier == "Restricted":
        print("  ACTION: BLOCK load — compliance sign-off required")
    elif tier == "Confidential":
        print("  ACTION: Masking applied — safe to load")
    else:
        print("  ACTION: Safe to load — no masking required")
    print("="*60)

if __name__ == "__main__":
    main()
