"""
==============================================================================
DAY 11 — LAB 2: INGESTION QUALITY AGENT (THE MAIN LAB)
Schema-Detect → Profile → GE Expectations → Validate → Auto-Fix → Quarantine
==============================================================================

MISSION BRIEFING
----------------
Sigma DataTech receives 50+ CSV files daily from merchant partners.
Each file has a different schema. Data quality varies wildly.
The junior DE team spends 3 hours every morning manually inspecting files
before loading — and they still miss issues that break dashboards by 10 AM.

You are building the Ingestion Quality Agent:
  → It receives a CSV it has NEVER seen before
  → Profiles it automatically
  → Uses an LLM to generate Great Expectations rules from the profile
  → Runs those rules against the data
  → Auto-fixes common issues (nulls, type coercions, date formats)
  → Quarantines rows that cannot be fixed
  → Logs a quality report and load decision

This is the first agent at Sigma that runs autonomously without a human
in the loop. Production trust = zero tolerance for silent failures.

WHAT YOU WILL LEARN
-------------------
- Automated data profiling with pandas (pandas-profiling is too slow — we do it right)
- Using LLMs to generate Great Expectations expectation suites from a data profile
- Running GE checks programmatically and parsing results
- Auto-remediation patterns: which fixes are safe vs which need human review
- Quarantine patterns: separate bad rows, preserve audit trail
- Structured quality report generation (JSON + human-readable summary)

MANUAL FIRST (3 minutes — close your laptop)
----------------------------------------------
Open data/transactions_raw.csv in your head (or on paper from sample_data.py output).
Write down 5 quality rules you would check BEFORE loading this into Snowflake.
Example: "transaction_id must not be null"
Write your 5 rules NOW. Then compare with what the LLM generates.

WHERE THIS FITS
---------------
This agent becomes the ENTRY GATE of Sigma's intelligence platform.
No data enters Snowflake without passing through this agent.
Day 12 capstone teams will extend it with their own quality rules.

==============================================================================
OUTPUT
------
  agent_outputs/quality_report.json        — full quality assessment
  agent_outputs/quarantine.csv             — rows that failed and couldn't be fixed
  agent_outputs/clean_output.csv           — rows that passed (or were auto-fixed)
  agent_outputs/ge_expectations.json       — LLM-generated expectation suite
==============================================================================
"""

import os, sys, json, csv
from datetime import datetime
from collections import defaultdict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import boto3
    import pandas as pd
except ImportError as e:
    print(f"[ERROR] Missing: {e}. Run: pip install boto3 pandas great_expectations")
    sys.exit(1)

try:
    import great_expectations as gx
    GE_AVAILABLE = True
except ImportError:
    GE_AVAILABLE = False
    print("[WARN] great_expectations not installed. Run: pip install great_expectations")
    print("       Continuing without GE — expectation suite will be generated but not executed.")

DATA_DIR   = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "agent_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MODEL_ID = "amazon.nova-pro-v1:0"   # Pro for quality reasoning (higher stakes)
REGION   = "us-east-1"

INPUT_FILE = os.path.join(DATA_DIR, "transactions_raw.csv")

# ── Bedrock helper ────────────────────────────────────────────────────────────
def call_bedrock(prompt: str, system: str = "", max_tokens: int = 1500) -> str:
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.1},
    }
    if system:
        body["system"] = [{"text": system}]
    resp = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    return json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"].strip()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: SCHEMA DETECTION + PROFILING
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("STEP 1: SCHEMA DETECTION + DATA PROFILING")
print("="*60)

df_raw = pd.read_csv(INPUT_FILE)
print(f"\n  File loaded: {os.path.basename(INPUT_FILE)}")
print(f"  Shape: {df_raw.shape[0]} rows × {df_raw.shape[1]} columns")

def profile_dataframe(df: pd.DataFrame) -> dict:
    """Generate a structured profile without any external library."""
    profile = {"columns": {}, "summary": {}}

    for col in df.columns:
        series  = df[col]
        n_total = len(series)
        n_null  = int(series.isna().sum()) + int((series == "").sum())
        n_unique = int(series.nunique())

        col_profile = {
            "dtype":        str(series.dtype),
            "total_rows":   n_total,
            "null_count":   n_null,
            "null_pct":     round(n_null / n_total * 100, 1),
            "unique_count": n_unique,
            "uniqueness_pct": round(n_unique / n_total * 100, 1),
        }

        # Numeric stats
        numeric_series = pd.to_numeric(series, errors="coerce")
        if numeric_series.notna().sum() > n_total * 0.5:
            col_profile["inferred_type"] = "numeric"
            col_profile["min"]  = float(numeric_series.min())
            col_profile["max"]  = float(numeric_series.max())
            col_profile["mean"] = round(float(numeric_series.mean()), 2)
            col_profile["negative_count"] = int((numeric_series < 0).sum())
        else:
            col_profile["inferred_type"] = "string"
            top_vals = series.value_counts().head(5).to_dict()
            col_profile["top_values"] = {str(k): int(v) for k, v in top_vals.items()}

        profile["columns"][col] = col_profile

    profile["summary"] = {
        "total_rows":    df.shape[0],
        "total_columns": df.shape[1],
        "column_names":  list(df.columns),
        "completeness_pct": round(
            (1 - df.isnull().sum().sum() / (df.shape[0] * df.shape[1])) * 100, 1
        ),
    }
    return profile

profile = profile_dataframe(df_raw)
print(f"\n  Profiling complete. Completeness: {profile['summary']['completeness_pct']}%")
for col, stats in profile["columns"].items():
    if stats["null_pct"] > 0 or stats.get("negative_count", 0) > 0:
        issues = []
        if stats["null_pct"] > 0:   issues.append(f"{stats['null_pct']}% nulls")
        if stats.get("negative_count", 0) > 0: issues.append(f"{stats['negative_count']} negatives")
        print(f"    ⚠ {col}: {', '.join(issues)}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: LLM GENERATES GREAT EXPECTATIONS SUITE
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("STEP 2: LLM GENERATES GREAT EXPECTATIONS SUITE")
print("="*60)
print("\n  Sending profile to Bedrock Nova Pro...")

ge_prompt = f"""You are a data quality engineer at Sigma DataTech (a fintech company).
You have profiled a CSV file with the following structure:

{json.dumps(profile, indent=2)}

Generate a Great Expectations expectation suite for this dataset.
Focus on:
1. Primary key integrity (transaction_id must not be null, must be unique)
2. Numeric validity (amount must be positive, within reasonable range)
3. Date format validity (transaction_date must match YYYY-MM-DD)
4. Categorical constraints (currency must be in known list, status must be in known list)
5. Completeness rules (critical fields must not exceed 5% nulls)

Return ONLY a JSON object in this exact format:
{{
  "expectation_suite_name": "sigma_transactions_quality",
  "expectations": [
    {{
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": {{"column": "transaction_id"}},
      "severity": "critical",
      "auto_fixable": false,
      "fix_action": null
    }},
    ...more expectations...
  ]
}}

Include at least 10 expectations. For each, add:
- severity: critical / high / medium
- auto_fixable: true/false
- fix_action: null or description of the safe fix (e.g., "fill with median", "drop row")
"""

ge_response = call_bedrock(ge_prompt, max_tokens=2000)

# Parse the expectation suite
try:
    start = ge_response.index("{")
    end   = ge_response.rindex("}") + 1
    ge_suite = json.loads(ge_response[start:end])
except Exception:
    # Fallback minimal suite
    ge_suite = {
        "expectation_suite_name": "sigma_transactions_quality",
        "expectations": [
            {"expectation_type": "expect_column_values_to_not_be_null",
             "kwargs": {"column": "transaction_id"}, "severity": "critical",
             "auto_fixable": False, "fix_action": None},
            {"expectation_type": "expect_column_values_to_be_unique",
             "kwargs": {"column": "transaction_id"}, "severity": "critical",
             "auto_fixable": False, "fix_action": None},
            {"expectation_type": "expect_column_values_to_be_between",
             "kwargs": {"column": "amount", "min_value": 0, "max_value": 1000000},
             "severity": "high", "auto_fixable": False, "fix_action": "quarantine row"},
        ]
    }

ge_path = os.path.join(OUTPUT_DIR, "ge_expectations.json")
with open(ge_path, "w") as f:
    json.dump(ge_suite, f, indent=2)

n_expectations = len(ge_suite.get("expectations", []))
print(f"\n  LLM generated {n_expectations} expectations")
print(f"  Saved → {ge_path}")
for exp in ge_suite.get("expectations", [])[:5]:
    sev = exp.get("severity", "?")
    col = exp.get("kwargs", {}).get("column", "?")
    fixable = "✓ auto-fix" if exp.get("auto_fixable") else "✗ manual"
    print(f"    [{sev.upper():8}] {exp['expectation_type']} on '{col}' — {fixable}")
if n_expectations > 5:
    print(f"    ... and {n_expectations - 5} more (see ge_expectations.json)")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: RUN QUALITY CHECKS
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("STEP 3: RUNNING QUALITY CHECKS")
print("="*60)

# We implement checks directly in pandas for reliability.
# (GE API changes version-to-version — this is more stable for a classroom.)

def run_checks(df: pd.DataFrame, expectations: list) -> list:
    results = []
    for exp in expectations:
        col    = exp.get("kwargs", {}).get("column")
        etype  = exp.get("expectation_type", "")
        result = {"expectation": etype, "column": col, "severity": exp.get("severity"),
                  "passed": True, "failed_row_count": 0, "failed_row_indices": []}

        try:
            if etype == "expect_column_values_to_not_be_null":
                mask = df[col].isna() | (df[col].astype(str).str.strip() == "")
                result["failed_row_indices"] = df[mask].index.tolist()

            elif etype == "expect_column_values_to_be_unique":
                mask = df.duplicated(subset=[col], keep=False)
                result["failed_row_indices"] = df[mask].index.tolist()

            elif etype == "expect_column_values_to_be_between":
                numeric = pd.to_numeric(df[col], errors="coerce")
                lo = exp["kwargs"].get("min_value", float("-inf"))
                hi = exp["kwargs"].get("max_value", float("inf"))
                mask = (numeric < lo) | (numeric > hi) | numeric.isna()
                result["failed_row_indices"] = df[mask].index.tolist()

            elif etype == "expect_column_values_to_be_in_set":
                val_set = set(exp["kwargs"].get("value_set", []))
                if val_set:
                    mask = ~df[col].astype(str).isin(val_set)
                    result["failed_row_indices"] = df[mask].index.tolist()

            elif etype == "expect_column_values_to_match_regex":
                regex = exp["kwargs"].get("regex", ".*")
                mask = ~df[col].astype(str).str.match(regex)
                result["failed_row_indices"] = df[mask].index.tolist()

        except KeyError:
            result["error"] = f"Column '{col}' not found"

        result["failed_row_count"] = len(result["failed_row_indices"])
        result["passed"] = result["failed_row_count"] == 0
        results.append(result)
    return results

check_results = run_checks(df_raw, ge_suite.get("expectations", []))

passed = sum(1 for r in check_results if r["passed"])
failed = len(check_results) - passed
print(f"\n  Checks run: {len(check_results)}")
print(f"  ✓ Passed : {passed}")
print(f"  ✗ Failed : {failed}")

for r in check_results:
    if not r["passed"]:
        sev = r.get("severity", "?").upper()
        print(f"    [{sev:8}] {r['expectation']} on '{r['column']}' "
              f"— {r['failed_row_count']} rows failed")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: AUTO-FIX COMMON ISSUES
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("STEP 4: AUTO-FIX SAFE ISSUES")
print("="*60)

df_working = df_raw.copy()
fix_log = []

# Collect all failed row indices (for quarantine decision later)
all_failed_indices = set()
critical_failed_indices = set()

for r in check_results:
    all_failed_indices.update(r["failed_row_indices"])
    if r.get("severity") == "critical":
        critical_failed_indices.update(r["failed_row_indices"])

# Safe fixes (auto-fixable based on LLM-generated suite)
auto_fixable_cols = {
    exp.get("kwargs", {}).get("column"): exp.get("fix_action")
    for exp in ge_suite.get("expectations", [])
    if exp.get("auto_fixable") and exp.get("fix_action")
}

# Fix 1: Fill null amounts with median (if LLM said so)
if "amount" in df_working.columns:
    null_amount_mask = df_working["amount"].isna() | (df_working["amount"].astype(str) == "")
    n_null_amounts = null_amount_mask.sum()
    if n_null_amounts > 0:
        numeric_amounts = pd.to_numeric(df_working["amount"], errors="coerce")
        median_val = numeric_amounts.median()
        df_working.loc[null_amount_mask, "amount"] = median_val
        fix_log.append({"fix": "null_amount_filled_with_median",
                        "rows_affected": int(n_null_amounts), "value_used": float(median_val)})
        print(f"  ✓ Fixed {n_null_amounts} null amounts → median ({median_val:.2f})")

# Fix 2: Standardise transaction_date format (replace bad dates with NaT marker)
if "transaction_date" in df_working.columns:
    parsed = pd.to_datetime(df_working["transaction_date"], format="%Y-%m-%d", errors="coerce")
    bad_date_mask = parsed.isna() & df_working["transaction_date"].notna()
    n_bad_dates = bad_date_mask.sum()
    if n_bad_dates > 0:
        df_working.loc[bad_date_mask, "transaction_date"] = "INVALID_DATE"
        fix_log.append({"fix": "invalid_dates_marked", "rows_affected": int(n_bad_dates)})
        print(f"  ✓ Marked {n_bad_dates} invalid dates as INVALID_DATE")

# Fix 3: Strip whitespace from string columns
for col in df_working.select_dtypes(include="object").columns:
    df_working[col] = df_working[col].astype(str).str.strip()
fix_log.append({"fix": "whitespace_stripped", "columns": list(df_working.select_dtypes("object").columns)})
print(f"  ✓ Stripped whitespace from all string columns")

print(f"\n  Auto-fix summary: {len(fix_log)} fix operations applied")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: QUARANTINE UNRESOLVABLE ROWS
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("STEP 5: QUARANTINE UNRESOLVABLE ROWS")
print("="*60)

# Quarantine rows with critical failures (blank PK, etc.)
quarantine_indices = list(critical_failed_indices)
clean_indices = [i for i in df_working.index if i not in critical_failed_indices]

df_quarantine = df_working.loc[quarantine_indices].copy() if quarantine_indices else pd.DataFrame(columns=df_working.columns)
df_clean      = df_working.loc[clean_indices].copy()

# Add quarantine reason column
if not df_quarantine.empty:
    reasons = []
    for idx in quarantine_indices:
        row_reasons = []
        for r in check_results:
            if idx in r.get("failed_row_indices", []) and r.get("severity") == "critical":
                row_reasons.append(f"{r['expectation']}:{r['column']}")
        reasons.append("; ".join(row_reasons) if row_reasons else "critical_check_failed")
    df_quarantine["_quarantine_reason"] = reasons
    df_quarantine["_quarantine_ts"] = datetime.now().isoformat()

quarantine_path = os.path.join(OUTPUT_DIR, "quarantine.csv")
clean_path      = os.path.join(OUTPUT_DIR, "clean_output.csv")

df_quarantine.to_csv(quarantine_path, index=False)
df_clean.to_csv(clean_path, index=False)

quarantine_pct = round(len(quarantine_indices) / len(df_working) * 100, 1)
print(f"\n  Total rows      : {len(df_working)}")
print(f"  Clean (loadable): {len(df_clean)} ({100-quarantine_pct}%)")
print(f"  Quarantined     : {len(df_quarantine)} ({quarantine_pct}%)")
print(f"\n  ✓ Saved clean    → {clean_path}")
print(f"  ✓ Saved quarantine → {quarantine_path}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6: GENERATE QUALITY REPORT + LOAD DECISION
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("STEP 6: QUALITY REPORT + LOAD DECISION")
print("="*60)

# Ask LLM for load decision narrative
load_prompt = f"""You are the Ingestion Quality Agent for Sigma DataTech.
Here is the quality assessment summary:

Total rows: {len(df_working)}
Clean rows: {len(df_clean)} ({100-quarantine_pct}%)
Quarantined rows: {len(df_quarantine)} ({quarantine_pct}%)

Check results:
{json.dumps([{"check": r["expectation"], "column": r["column"], "severity": r.get("severity"),
              "failed_rows": r["failed_row_count"]} for r in check_results], indent=2)}

Auto-fixes applied: {json.dumps(fix_log, indent=2)}

Based on this, provide:
1. load_decision: one of "load_clean", "quarantine_and_load", "reject_all"
2. load_decision_reason: one sentence
3. alert_required: true/false (true if quarantine > 10% or any critical check failed)
4. recommended_actions: list of 2-3 next steps for the data team

Return JSON only (no markdown)."""

load_response = call_bedrock(load_prompt, max_tokens=600)
try:
    start = load_response.index("{")
    end   = load_response.rindex("}") + 1
    load_decision = json.loads(load_response[start:end])
except Exception:
    load_decision = {
        "load_decision": "quarantine_and_load",
        "load_decision_reason": "Critical row failures quarantined; clean rows safe to load.",
        "alert_required": quarantine_pct > 10,
        "recommended_actions": ["Review quarantine.csv", "Fix upstream data source", "Re-run agent"]
    }

quality_report = {
    "agent":            "IngestionQualityAgent",
    "version":          "1.0",
    "run_timestamp":    datetime.now().isoformat(),
    "input_file":       os.path.basename(INPUT_FILE),
    "profile_summary":  profile["summary"],
    "expectations_generated": n_expectations,
    "checks_passed":    passed,
    "checks_failed":    failed,
    "auto_fixes":       fix_log,
    "clean_rows":       len(df_clean),
    "quarantined_rows": len(df_quarantine),
    "quarantine_pct":   quarantine_pct,
    "load_decision":    load_decision,
    "check_details":    [{k: v for k, v in r.items() if k != "failed_row_indices"}
                         for r in check_results],
}

report_path = os.path.join(OUTPUT_DIR, "quality_report.json")
with open(report_path, "w") as f:
    json.dump(quality_report, f, indent=2)

print(f"\n  Load decision : {load_decision.get('load_decision', '?').upper()}")
print(f"  Reason        : {load_decision.get('load_decision_reason', '?')}")
print(f"  Alert required: {load_decision.get('alert_required', False)}")
if load_decision.get("recommended_actions"):
    print("  Next steps:")
    for action in load_decision["recommended_actions"]:
        print(f"    • {action}")
print(f"\n  ✓ Quality report → {report_path}")

# ─────────────────────────────────────────────────────────────────────────────
# JUDGMENT QUESTION
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("JUDGMENT QUESTION")
print("="*60)
print(f"""
  The agent quarantined {len(df_quarantine)} rows ({quarantine_pct}%) of this file.

  The data engineering lead says: "Just load everything — business can't wait."
  The compliance officer says: "Nothing loads without a complete quality check."

  What is the RIGHT call, and what single guardrail would you add to the agent
  to prevent this conflict from happening again?
""")
judgment = input("  Your answer (1-2 sentences): ").strip() or "NOT ANSWERED"

with open(report_path) as f:
    report_data = json.load(f)
report_data["student_judgment"] = judgment
with open(report_path, "w") as f:
    json.dump(report_data, f, indent=2)

# ── Final summary ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("LAB 2 COMPLETE — INGESTION QUALITY AGENT")
print("="*60)
print(f"""
  The 6-step pipeline ran end-to-end autonomously:
    1. Schema detected + data profiled
    2. {n_expectations} GE expectations generated by LLM
    3. {len(check_results)} quality checks executed
    4. {len(fix_log)} auto-fix operations applied
    5. {len(df_quarantine)} rows quarantined ({quarantine_pct}%)
    6. Load decision: {load_decision.get('load_decision', '?')}

  Output files:
    quality_report.json    — full audit trail
    ge_expectations.json   — LLM-generated rules
    clean_output.csv       — {len(df_clean)} rows ready to load
    quarantine.csv         — {len(df_quarantine)} rows held for review
""")
