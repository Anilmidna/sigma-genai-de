"""
==============================================================================
DAY 13 — AGENT 3: INGESTION QUALITY AGENT
==============================================================================
Profiles the latest S3 Bronze file, generates Great Expectations rules via LLM,
runs quality checks, auto-fixes safe issues, quarantines bad rows,
makes a load decision.

Usage:
  python agents/ingestion_quality_agent.py \
    --bucket sigma-datatech-anil \
    --prefix bronze/transactions/ \
    --region us-east-1

Output:
  agent_outputs/quality_report_<timestamp>.json
  agent_outputs/quarantine_<timestamp>.csv
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

def call_bedrock(prompt, region="us-east-1", max_tokens=2000):
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

def profile_dataframe(df):
    """Generate a concise data profile without external libraries."""
    profile = {"columns": {}, "summary": {}}
    for col in df.columns:
        series  = df[col]
        n_total = len(series)
        n_null  = int(series.isna().sum()) + int((series.astype(str) == "").sum())
        n_unique = int(series.nunique())
        cp = {
            "dtype":       str(series.dtype),
            "null_count":  n_null,
            "null_pct":    round(n_null / n_total * 100, 1),
            "unique_count":n_unique,
        }
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().sum() > n_total * 0.5:
            cp["inferred_type"]     = "numeric"
            cp["min"]               = float(numeric.min())
            cp["max"]               = float(numeric.max())
            cp["mean"]              = round(float(numeric.mean()), 2)
            cp["negative_count"]    = int((numeric < 0).sum())
        else:
            cp["inferred_type"] = "string"
            cp["top_values"]    = {str(k): int(v)
                                   for k, v in series.value_counts().head(5).items()}
        profile["columns"][col] = cp
    profile["summary"] = {
        "total_rows":       df.shape[0],
        "total_columns":    df.shape[1],
        "column_names":     list(df.columns),
        "completeness_pct": round(
            (1 - df.isnull().sum().sum() / (df.shape[0] * df.shape[1])) * 100, 1),
    }
    return profile

def generate_ge_expectations(profile, region):
    """Ask Bedrock to generate a GE expectation suite from the profile."""
    prompt = f"""You are a data quality engineer at Sigma DataTech (fintech).
Generate a Great Expectations expectation suite for this dataset profile:

{json.dumps(profile, indent=2)}

Generate at least 8 expectations covering:
- Primary key not null and unique
- Amount must be positive and within range
- Date must match YYYY-MM-DD
- Currency must be in known set: INR, USD, EUR, GBP
- Status must be in known set: completed, pending, failed
- Critical fields must have < 5% nulls

Return JSON only:
{{
  "expectation_suite_name": "sigma_transactions_quality",
  "expectations": [
    {{
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": {{"column": "transaction_id"}},
      "severity": "critical",
      "auto_fixable": false,
      "fix_action": null
    }}
  ]
}}"""
    response = call_bedrock(prompt, region)
    try:
        start = response.index("{")
        end   = response.rindex("}") + 1
        return json.loads(response[start:end])
    except Exception:
        return {
            "expectation_suite_name": "sigma_transactions_quality",
            "expectations": [
                {"expectation_type": "expect_column_values_to_not_be_null",
                 "kwargs": {"column": "transaction_id"}, "severity": "critical",
                 "auto_fixable": False, "fix_action": None},
                {"expectation_type": "expect_column_values_to_be_between",
                 "kwargs": {"column": "amount", "min_value": 0, "max_value": 5000000},
                 "severity": "high", "auto_fixable": False, "fix_action": "quarantine"},
                {"expectation_type": "expect_column_values_to_be_in_set",
                 "kwargs": {"column": "currency", "value_set": ["INR","USD","EUR","GBP"]},
                 "severity": "medium", "auto_fixable": False, "fix_action": "quarantine"},
                {"expectation_type": "expect_column_values_to_be_in_set",
                 "kwargs": {"column": "status", "value_set": ["completed","pending","failed"]},
                 "severity": "medium", "auto_fixable": True,
                 "fix_action": "fill with 'unknown'"},
            ]
        }

def run_checks(df, expectations):
    """Run each expectation against the DataFrame."""
    results = []
    for exp in expectations:
        col   = exp.get("kwargs", {}).get("column")
        etype = exp.get("expectation_type", "")
        r     = {"expectation": etype, "column": col,
                 "severity": exp.get("severity"),
                 "passed": True, "failed_indices": []}
        try:
            if etype == "expect_column_values_to_not_be_null":
                mask = df[col].isna() | (df[col].astype(str).str.strip() == "")
                r["failed_indices"] = df[mask].index.tolist()
            elif etype == "expect_column_values_to_be_unique":
                mask = df.duplicated(subset=[col], keep=False)
                r["failed_indices"] = df[mask].index.tolist()
            elif etype == "expect_column_values_to_be_between":
                num  = pd.to_numeric(df[col], errors="coerce")
                lo   = exp["kwargs"].get("min_value", float("-inf"))
                hi   = exp["kwargs"].get("max_value", float("inf"))
                mask = (num < lo) | (num > hi) | num.isna()
                r["failed_indices"] = df[mask].index.tolist()
            elif etype == "expect_column_values_to_be_in_set":
                val_set = set(exp["kwargs"].get("value_set", []))
                if val_set:
                    mask = ~df[col].astype(str).isin(val_set)
                    r["failed_indices"] = df[mask].index.tolist()
            elif etype == "expect_column_values_to_match_regex":
                pattern = exp["kwargs"].get("regex", ".*")
                mask    = ~df[col].astype(str).str.match(pattern)
                r["failed_indices"] = df[mask].index.tolist()
        except KeyError:
            r["error"] = f"Column '{col}' not found"

        r["failed_count"] = len(r["failed_indices"])
        r["passed"]       = r["failed_count"] == 0
        results.append(r)
    return results

def main():
    parser = argparse.ArgumentParser(description="Ingestion Quality Agent")
    parser.add_argument("--bucket",  required=True)
    parser.add_argument("--prefix",  required=True)
    parser.add_argument("--region",  default="us-east-1")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("INGESTION QUALITY AGENT — 6-STEP PIPELINE")
    print("="*60)

    s3  = boto3.client("s3", region_name=args.region)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── Step 1: Profile ───────────────────────────────────────────────────────
    print("\n  STEP 1: SCHEMA DETECT + PROFILE")
    key = get_latest_s3_file(s3, args.bucket, args.prefix)
    if not key:
        print("  [WARN] No files in S3. Run data_generator.py first.")
        sys.exit(0)
    print(f"  File: {key}")

    df      = read_s3_json_gz(s3, args.bucket, key)
    profile = profile_dataframe(df)
    print(f"  Rows: {profile['summary']['total_rows']} | "
          f"Columns: {profile['summary']['total_columns']} | "
          f"Completeness: {profile['summary']['completeness_pct']}%")
    for col, stats in profile["columns"].items():
        issues = []
        if stats["null_pct"] > 0:
            issues.append(f"{stats['null_pct']}% nulls")
        if stats.get("negative_count", 0) > 0:
            issues.append(f"{stats['negative_count']} negatives")
        if issues:
            print(f"  WARNING {col}: {', '.join(issues)}")

    # ── Step 2: Generate GE expectations ─────────────────────────────────────
    print("\n  STEP 2: LLM GENERATES GE EXPECTATIONS (Bedrock Nova Pro)...")
    ge_suite = generate_ge_expectations(profile, args.region)
    n_exp    = len(ge_suite.get("expectations", []))
    print(f"  Generated {n_exp} expectations:")
    for exp in ge_suite.get("expectations", [])[:5]:
        sev = exp.get("severity","?").upper()
        col = exp.get("kwargs",{}).get("column","?")
        print(f"    [{sev:8}] {exp['expectation_type']} on '{col}'")
    if n_exp > 5:
        print(f"    ... and {n_exp-5} more")

    # ── Step 3: Run checks ────────────────────────────────────────────────────
    print("\n  STEP 3: RUNNING QUALITY CHECKS...")
    check_results = run_checks(df, ge_suite.get("expectations", []))
    passed = sum(1 for r in check_results if r["passed"])
    failed = len(check_results) - passed
    print(f"  Checks: {len(check_results)} | Passed: {passed} | Failed: {failed}")
    for r in check_results:
        if not r["passed"]:
            sev = r.get("severity","?").upper()
            print(f"  FAIL [{sev:8}] {r['expectation']} on '{r['column']}' "
                  f"— {r['failed_count']} rows")

    # ── Step 4: Auto-fix ─────────────────────────────────────────────────────
    print("\n  STEP 4: AUTO-FIX SAFE ISSUES...")
    df_work  = df.copy()
    fix_log  = []

    # Strip whitespace
    for col in df_work.select_dtypes(include="object").columns:
        df_work[col] = df_work[col].astype(str).str.strip()
    fix_log.append({"fix": "whitespace_stripped"})
    print("  Stripped whitespace from all string columns")

    # Fill null status with 'unknown' if expectation says auto_fixable
    for exp in ge_suite.get("expectations", []):
        if (exp.get("auto_fixable") and
            exp.get("expectation_type") == "expect_column_values_to_be_in_set" and
            exp.get("kwargs", {}).get("column") == "status"):
            val_set = set(exp["kwargs"].get("value_set", []))
            mask    = ~df_work["status"].isin(val_set)
            n_fixed = mask.sum()
            if n_fixed > 0:
                df_work.loc[mask, "status"] = "unknown"
                fix_log.append({"fix": "status_filled_unknown", "rows": int(n_fixed)})
                print(f"  Fixed {n_fixed} unknown status values → 'unknown'")

    # ── Step 5: Quarantine ────────────────────────────────────────────────────
    print("\n  STEP 5: QUARANTINE CRITICAL FAILURES...")
    critical_indices = set()
    for r in check_results:
        if r.get("severity") == "critical":
            critical_indices.update(r["failed_indices"])

    df_quarantine = df_work.loc[list(critical_indices)].copy() if critical_indices else pd.DataFrame()
    df_clean      = df_work.loc[[i for i in df_work.index if i not in critical_indices]].copy()

    if not df_quarantine.empty:
        reasons = []
        for idx in list(critical_indices):
            row_reasons = [
                f"{r['expectation']}:{r['column']}"
                for r in check_results
                if idx in r.get("failed_indices", []) and r.get("severity") == "critical"
            ]
            reasons.append("; ".join(row_reasons) or "critical_check_failed")
        df_quarantine["_quarantine_reason"] = reasons
        df_quarantine["_quarantined_at"]    = datetime.now().isoformat()

    quarantine_path = os.path.join(OUTPUT_DIR, f"quarantine_{ts}.csv")
    df_quarantine.to_csv(quarantine_path, index=False)
    q_pct = round(len(df_quarantine) / len(df_work) * 100, 1) if len(df_work) > 0 else 0
    print(f"  Total rows    : {len(df_work)}")
    print(f"  Clean (load)  : {len(df_clean)} ({100-q_pct}%)")
    print(f"  Quarantined   : {len(df_quarantine)} ({q_pct}%)")

    # ── Step 6: Load decision + report ───────────────────────────────────────
    print("\n  STEP 6: LOAD DECISION...")
    decision_prompt = f"""You are the Ingestion Quality Agent for Sigma DataTech.

Quality summary:
- Total rows: {len(df_work)}
- Clean rows: {len(df_clean)} ({100-q_pct}%)
- Quarantined: {len(df_quarantine)} ({q_pct}%)
- Checks passed: {passed}/{len(check_results)}
- Auto-fixes applied: {len(fix_log)}

Make a load decision:
{{
  "load_decision": "load_clean / quarantine_and_load / reject_all",
  "reason": "one sentence",
  "alert_required": true or false,
  "next_steps": ["step1", "step2"]
}}
Return JSON only."""

    resp = call_bedrock(decision_prompt, args.region, max_tokens=400)
    try:
        start = resp.index("{"); end = resp.rindex("}") + 1
        decision = json.loads(resp[start:end])
    except Exception:
        decision = {
            "load_decision": "quarantine_and_load" if q_pct < 20 else "reject_all",
            "reason":        f"{q_pct}% quarantined — clean rows safe to load",
            "alert_required":q_pct > 10 or failed > 0,
            "next_steps":    ["Review quarantine.csv", "Fix upstream data source", "Re-run agent"],
        }

    print(f"  Decision      : {decision['load_decision'].upper()}")
    print(f"  Reason        : {decision['reason']}")
    print(f"  Alert needed  : {decision['alert_required']}")

    # Judgment question
    print("\n" + "="*60)
    print("JUDGMENT QUESTION")
    print("="*60)
    print(f"""
  The agent quarantined {len(df_quarantine)} rows ({q_pct}%) and made
  the decision: {decision['load_decision'].upper()}

  Your business analyst says GMV is down today. Is it because of
  the quarantine? How do you check? What is your first action?
""")
    judgment = input("  Your answer (1-2 sentences): ").strip() or "NOT ANSWERED"

    # Save report
    report = {
        "agent":             "IngestionQualityAgent",
        "timestamp":         datetime.now().isoformat(),
        "file_processed":    key,
        "profile_summary":   profile["summary"],
        "expectations_generated": n_exp,
        "checks_passed":     passed,
        "checks_failed":     failed,
        "auto_fixes":        fix_log,
        "clean_rows":        len(df_clean),
        "quarantined_rows":  len(df_quarantine),
        "quarantine_pct":    q_pct,
        "load_decision":     decision,
        "check_details": [
            {k: v for k, v in r.items() if k != "failed_indices"}
            for r in check_results
        ],
        "student_judgment":  judgment,
    }
    report_path = os.path.join(OUTPUT_DIR, f"quality_report_{ts}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  ✓ Quality report  : {report_path}")
    print(f"  ✓ Quarantine file : {quarantine_path}")
    print("="*60)
    print(f"\n  {len(df_clean)} clean rows ready to load to Databricks Silver.")
    print(f"  {len(df_quarantine)} quarantined rows require human review.")
    print("="*60)

if __name__ == "__main__":
    main()
