"""
Day 8 — Sprint 5: Data Observability with Evidently AI
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
MISSION:
  Pipeline reviewed, documented, tested, CI/CD live, SLOs set.
  The final layer: observability.

  Not a code dashboard — a DATA observability report. This shows
  how your Bronze / Silver / Gold layers compare, where data
  quality degrades between layers, and what the DataOps team
  monitors every morning before the analytics team arrives.

  Tool: Evidently AI — open source, used at Netflix, Booking.com,
  Sber. Generates HTML reports your team can open in any browser.

  This is how you know your pipeline is healthy before your
  manager asks.

MANUAL FIRST (do this BEFORE running the script):
  Look at sample_data.py. Bronze has 21 rows; Silver should have
  fewer after filtering. Take 2 minutes — write down:
    1. How many Bronze rows do you expect to DROP in Silver? Why?
    2. Which column is most likely to show data drift between
       Bronze and Silver? (Hint: what does the Silver transform do?)
    3. What would you put in a "DataOps Morning Report" — name
       3 metrics you'd check before the analytics team arrives.
  Write your answers first. Then run the script.

WHERE THIS FITS IN THE PLATFORM:
  Sprint 4 (4_ci_slo.py):     SLOs define what "healthy" means
  Sprint 5 (THIS):            Evidently measures whether we ARE healthy
  Day 12:                     A self-heal agent reads observability
                              output and auto-fixes pipeline failures

HOW TO RUN:
  cd repo/day8/lab
  python 5_observability.py

DEPENDENCIES:
  pip install evidently pandas duckdb

OUTPUT:
  devops_brain/observability/silver_quality_report.html
  devops_brain/observability/bronze_silver_drift_report.html
  devops_brain/observability/morning_report.md
  devops_brain/observability_report.json

SPEND 5 MINUTES READING THIS FILE. YOU HAVE A QUIZ ON IT.
═══════════════════════════════════════════════════════════════
"""

import sys
import os
import json
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import boto3
except ImportError:
    print("[ERROR] boto3 not installed. Run: pip install boto3")
    sys.exit(1)

try:
    import duckdb
except ImportError:
    print("[ERROR] duckdb not installed. Run: pip install duckdb")
    print("        DuckDB is needed to load Bronze/Silver/Gold data.")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("[ERROR] pandas not installed. Run: pip install pandas")
    sys.exit(1)

# Evidently import — graceful fallback if not installed
try:
    from evidently.report import Report
    from evidently.metric_preset import DataQualityPreset, DataDriftPreset
    EVIDENTLY_AVAILABLE = True
except ImportError:
    EVIDENTLY_AVAILABLE = False
    print()
    print("  [WARN] Evidently not installed.")
    print("  Install Evidently for the full HTML report: pip install evidently")
    print("  Running in FALLBACK MODE — DuckDB SQL checks instead of HTML reports.")
    print()

# ── Configuration ──────────────────────────────────────────────────────────────
MODEL_ID_LITE  = "amazon.nova-lite-v1:0"
REGION         = "us-east-1"
LAB_DIR        = os.path.dirname(os.path.abspath(__file__))
DB_PATH        = os.path.join(LAB_DIR, "sigma_platform.duckdb")
OUTPUT_DIR     = os.path.join(LAB_DIR, "devops_brain")
OBS_DIR        = os.path.join(OUTPUT_DIR, "observability")
os.makedirs(OBS_DIR, exist_ok=True)

bedrock = boto3.client("bedrock-runtime", region_name=REGION)


# ── Bedrock helper ─────────────────────────────────────────────────────────────
def call_bedrock_lite(prompt: str, max_tokens: int = 2000) -> tuple[str, dict]:
    """Call Bedrock Nova Lite and return (text, usage_dict)."""
    response = bedrock.invoke_model(
        modelId=MODEL_ID_LITE,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.2},
        }),
    )
    result = json.loads(response["body"].read())
    text   = result["output"]["message"]["content"][0]["text"]
    usage  = result.get("usage", {})
    return text, usage


# ── Step 1: Load data from DuckDB ─────────────────────────────────────────────
def load_dataframes() -> tuple:
    """
    Load Bronze, Silver, and Gold tables from sigma_platform.duckdb.
    Returns (bronze_df, silver_df, gold_df).
    Raises SystemExit with a clear message if DB is missing.
    """
    if not os.path.exists(DB_PATH):
        print("[ERROR] sigma_platform.duckdb not found.")
        print("        Run python 0_setup_duckdb.py first.")
        sys.exit(1)

    con = duckdb.connect(DB_PATH, read_only=True)
    bronze_df = con.execute("SELECT * FROM bronze_transactions").df()
    silver_df = con.execute("SELECT * FROM silver_transactions").df()
    gold_df   = con.execute("SELECT * FROM gold_merchant_performance").df()
    con.close()

    print(f"  Loaded bronze_transactions: {len(bronze_df)} rows, {len(bronze_df.columns)} columns")
    print(f"  Loaded silver_transactions: {len(silver_df)} rows, {len(silver_df.columns)} columns")
    print(f"  Loaded gold_merchant_performance: {len(gold_df)} rows, {len(gold_df.columns)} columns")
    print(f"  Rows dropped Bronze -> Silver: {len(bronze_df) - len(silver_df)}")

    return bronze_df, silver_df, gold_df


# ── Step 2: Evidently Data Quality Report (Silver) ────────────────────────────
def run_quality_report(silver_df: pd.DataFrame) -> dict:
    """
    Generate an Evidently DataQualityReport for the Silver layer.
    Returns a dict of key metrics extracted from the JSON result.
    """
    print("\n[Evidently] Step 2: Generating DataQualityReport for Silver layer...")

    report = Report(metrics=[DataQualityPreset()])
    # Evidently needs a reference — use the Silver DF as both current and reference
    # (quality report does not require a separate reference dataset)
    report.run(current_data=silver_df, reference_data=None)

    html_path = os.path.join(OBS_DIR, "silver_quality_report.html")
    report.save_html(html_path)
    print(f"[OK] Saved: devops_brain/observability/silver_quality_report.html")

    # Extract key metrics from the JSON result for downstream use
    result_dict = report.as_dict()
    metrics_summary = _extract_quality_summary(result_dict, silver_df)
    return metrics_summary


def _extract_quality_summary(result_dict: dict, df: pd.DataFrame) -> dict:
    """Pull headline numbers from Evidently JSON output."""
    # Compute null rates per column directly from pandas (simpler than parsing Evidently JSON)
    null_pcts = {col: round(df[col].isna().mean() * 100, 2) for col in df.columns}
    cols_with_nulls = {k: v for k, v in null_pcts.items() if v > 0}

    summary = {
        "total_rows":        len(df),
        "total_columns":     len(df.columns),
        "null_rates_pct":    null_pcts,
        "columns_with_nulls": cols_with_nulls,
        "unique_statuses":   df["status"].nunique() if "status" in df.columns else None,
        "status_counts":     df["status"].value_counts().to_dict() if "status" in df.columns else {},
        "amount_min":        float(df["amount"].min()) if "amount" in df.columns else None,
        "amount_max":        float(df["amount"].max()) if "amount" in df.columns else None,
        "amount_mean":       round(float(df["amount"].mean()), 2) if "amount" in df.columns else None,
    }
    return summary


# ── Step 3: Evidently Data Drift Report (Bronze vs Silver) ───────────────────
def run_drift_report(bronze_df: pd.DataFrame, silver_df: pd.DataFrame) -> dict:
    """
    Generate an Evidently DataDriftReport comparing Bronze (reference) vs Silver (current).
    This shows which columns changed distribution after the Silver transform.
    """
    print("[Evidently] Step 3: Generating DataDriftReport (Bronze vs Silver)...")

    # Align columns: only compare columns that exist in both layers
    shared_cols = [c for c in bronze_df.columns if c in silver_df.columns
                   and c not in ("ingestion_timestamp",)]

    ref_df  = bronze_df[shared_cols].copy()
    curr_df = silver_df[shared_cols].copy()

    # Evidently drift needs equal-or-larger reference set
    # If Silver has fewer rows (expected), pad reference to Silver size for comparison
    # (We take a sample of Bronze the same size as Silver for a fair comparison)
    if len(ref_df) > len(curr_df):
        ref_df = ref_df.sample(n=len(curr_df), random_state=42)

    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=ref_df, current_data=curr_df)

    html_path = os.path.join(OBS_DIR, "bronze_silver_drift_report.html")
    report.save_html(html_path)
    print(f"[OK] Saved: devops_brain/observability/bronze_silver_drift_report.html")

    # Extract drift summary
    result_dict = report.as_dict()
    drift_summary = _extract_drift_summary(result_dict, shared_cols)
    return drift_summary


def _extract_drift_summary(result_dict: dict, columns: list) -> dict:
    """Pull drift flags from Evidently JSON output."""
    # Walk the nested metrics structure to find dataset drift result
    drifted_cols = []
    drift_share  = None
    dataset_drifted = False

    try:
        for metric in result_dict.get("metrics", []):
            result = metric.get("result", {})
            if "drift_share" in result:
                drift_share     = result["drift_share"]
                dataset_drifted = result.get("dataset_drift", False)
                for col, col_result in result.get("drift_by_columns", {}).items():
                    if col_result.get("drift_detected", False):
                        drifted_cols.append(col)
    except Exception:
        pass

    return {
        "columns_compared": columns,
        "dataset_drifted":  dataset_drifted,
        "drift_share":      drift_share,
        "drifted_columns":  drifted_cols,
    }


# ── Fallback: DuckDB SQL checks (when Evidently not installed) ────────────────
def run_fallback_checks(bronze_df: pd.DataFrame, silver_df: pd.DataFrame, gold_df: pd.DataFrame) -> tuple[dict, dict]:
    """
    Run equivalent quality and drift checks using pandas when Evidently is unavailable.
    Returns (quality_summary, drift_summary).
    """
    print("\n[FALLBACK] Running DuckDB/pandas quality checks (Evidently not installed)...")

    # Quality checks on Silver
    quality_summary = _extract_quality_summary({}, silver_df)

    # Drift approximation: compare value distributions for key columns
    drifted_cols = []
    shared_cols  = [c for c in bronze_df.columns if c in silver_df.columns
                    and c not in ("ingestion_timestamp",)]
    for col in shared_cols:
        if bronze_df[col].dtype == object:
            b_vals = set(bronze_df[col].dropna().unique())
            s_vals = set(silver_df[col].dropna().unique())
            if b_vals != s_vals:
                drifted_cols.append(col)

    drift_summary = {
        "columns_compared": shared_cols,
        "dataset_drifted":  len(drifted_cols) > 0,
        "drift_share":      round(len(drifted_cols) / max(len(shared_cols), 1), 2),
        "drifted_columns":  drifted_cols,
        "note":             "Fallback mode — install evidently for HTML reports",
    }

    # Save fallback text report
    fallback_path = os.path.join(OBS_DIR, "fallback_quality_report.txt")
    with open(fallback_path, "w", encoding="utf-8") as f:
        f.write("DATA QUALITY FALLBACK REPORT (pandas checks)\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Silver rows:       {quality_summary['total_rows']}\n")
        f.write(f"Silver columns:    {quality_summary['total_columns']}\n")
        f.write(f"Amount range:      {quality_summary['amount_min']} - {quality_summary['amount_max']}\n")
        f.write(f"Amount mean:       {quality_summary['amount_mean']}\n")
        f.write(f"\nNull rates:\n")
        for col, pct in quality_summary["null_rates_pct"].items():
            flag = " <-- HAS NULLS" if pct > 0 else ""
            f.write(f"  {col:<30} {pct:.1f}%{flag}\n")
        f.write(f"\nStatus distribution:\n")
        for status, count in quality_summary["status_counts"].items():
            f.write(f"  {status:<15} {count}\n")
        f.write(f"\nColumns with value drift (Bronze vs Silver):\n")
        for col in drifted_cols:
            f.write(f"  {col}\n")
        if not drifted_cols:
            f.write("  None detected\n")

    print(f"[OK] Saved: devops_brain/observability/fallback_quality_report.txt")
    print("  Install Evidently for the full HTML report: pip install evidently")

    return quality_summary, drift_summary


# ── Step 4: Bedrock DataOps Morning Report ────────────────────────────────────
def generate_morning_report(quality_summary: dict, drift_summary: dict, gold_df: pd.DataFrame) -> tuple[str, dict]:
    """
    Ask Nova Lite to write a 5-bullet DataOps Morning Report from the
    Evidently/fallback results. This is the summary the on-call engineer
    reads at 08:00 before the analytics dashboard opens.
    """
    # Summarise gold layer stats for the prompt
    gold_stats = {}
    if not gold_df.empty:
        gold_stats = {
            "total_merchants":    int(gold_df["merchant_id"].nunique()),
            "total_revenue":      round(float(gold_df["total_revenue"].sum()), 2),
            "avg_failure_rate":   round(float(gold_df["failure_rate_pct"].mean()), 2),
            "max_failure_rate":   round(float(gold_df["failure_rate_pct"].max()), 2),
            "merchant_max_fail":  gold_df.loc[gold_df["failure_rate_pct"].idxmax(), "merchant_name"]
                                  if "merchant_name" in gold_df.columns else "unknown",
        }

    prompt = f"""You are a DataOps engineer writing the daily morning report for the Sigma DataTech
data pipeline. The analytics team reads this at 08:00 IST before opening the dashboard.

PIPELINE HEALTH DATA (from last run):

Silver Layer Quality:
  - Total rows: {quality_summary.get('total_rows', '?')}
  - Columns with nulls: {list(quality_summary.get('columns_with_nulls', {}).keys())}
  - Transaction status breakdown: {quality_summary.get('status_counts', {})}
  - Amount range: {quality_summary.get('amount_min', '?')} to {quality_summary.get('amount_max', '?')}
  - Amount mean: {quality_summary.get('amount_mean', '?')}

Bronze → Silver Drift:
  - Dataset drifted: {drift_summary.get('dataset_drifted', '?')}
  - Drift share: {drift_summary.get('drift_share', '?')}
  - Drifted columns: {drift_summary.get('drifted_columns', [])}

Gold Layer:
  - Active merchants: {gold_stats.get('total_merchants', '?')}
  - Total revenue: {gold_stats.get('total_revenue', '?')}
  - Average failure rate: {gold_stats.get('avg_failure_rate', '?')}%
  - Highest failure rate: {gold_stats.get('max_failure_rate', '?')}% ({gold_stats.get('merchant_max_fail', '?')})

Write a DATAOPS MORNING REPORT as a Markdown file with EXACTLY:
- A one-line date header: "## DataOps Morning Report — <today's date>"
- A "### Pipeline Status" section: HEALTHY / DEGRADED / CRITICAL (pick one, justify in one sentence)
- A "### 5 Key Findings" section: exactly 5 bullet points
  Each bullet: a specific metric or observation — what's the value, is it OK, why does it matter?
- A "### Alerts to Watch" section: 1-3 bullet points — what would trigger an alert today?
- A "### Recommended Actions" section: 1-3 bullet points — what should the team do before 10 AM?

Be specific — use the actual numbers from the data above. No generic placeholders.
OUTPUT: Pure Markdown. No code fences around the whole document."""

    print("\n[Bedrock Nova Lite] Step 4: Generating DataOps Morning Report...")
    text, usage = call_bedrock_lite(prompt, max_tokens=1500)

    # Strip any wrapping fences the model may add
    if text.strip().startswith("```"):
        text = text.strip()
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]

    report_path = os.path.join(OBS_DIR, "morning_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(text)

    tokens_in  = usage.get("inputTokens", "?")
    tokens_out = usage.get("outputTokens", "?")
    print(f"[OK] Saved: devops_brain/observability/morning_report.md")
    print(f"     Tokens: {tokens_in} in / {tokens_out} out")
    print()
    # Print the report inline so students see it in the terminal
    print("─" * 65)
    for line in text.splitlines()[:30]:        # first 30 lines in terminal
        print(f"  {line}")
    if len(text.splitlines()) > 30:
        print(f"  ... (see morning_report.md for full report)")
    print("─" * 65)

    return text, usage


# ── Step 5: Combined observability report ─────────────────────────────────────
def save_observability_report(
    quality_summary: dict,
    drift_summary: dict,
    morning_report_text: str,
    bedrock_usage: dict,
    student_judgment: str,
    evidently_mode: str,
) -> str:
    """Assemble and save observability_report.json."""
    report = {
        "sprint":           "observability",
        "generated_at":     datetime.now().isoformat(),
        "evidently_mode":   evidently_mode,
        "model_used":       MODEL_ID_LITE,
        "token_usage": {
            "morning_report": {
                "input":  bedrock_usage.get("inputTokens", 0),
                "output": bedrock_usage.get("outputTokens", 0),
            }
        },
        "silver_quality":   quality_summary,
        "bronze_silver_drift": drift_summary,
        "files_generated": [
            "devops_brain/observability/silver_quality_report.html"
            if evidently_mode == "full" else
            "devops_brain/observability/fallback_quality_report.txt",
            "devops_brain/observability/bronze_silver_drift_report.html"
            if evidently_mode == "full" else "N/A (fallback mode)",
            "devops_brain/observability/morning_report.md",
            "devops_brain/observability_report.json",
        ],
        "student_judgment": student_judgment if student_judgment.strip() else "NOT ANSWERED",
    }

    out_path = os.path.join(OUTPUT_DIR, "observability_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    return out_path


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    # ── Manual First reminder ─────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  MANUAL FIRST — Do This Before Running!")
    print("=" * 65)
    print("  Look at sample_data.py. Think about Bronze vs Silver.")
    print("  Write down (2 minutes — no script yet):")
    print()
    print("    1. How many Bronze rows will be DROPPED in Silver? Why?")
    print("    2. Which column is most likely to drift Bronze -> Silver?")
    print("    3. Three metrics you'd put in an 08:00 morning health report")
    print()
    print("  Keep your notes. You'll see what Evidently + AI produce.")
    print("=" * 65)
    input("  [Press Enter when ready to run the observability checks] ")

    print("\n" + "=" * 65)
    print("  SPRINT 5: Data Observability — Evidently AI + Bedrock")
    print("  Sigma Intelligence Platform | Day 8")
    print("=" * 65)

    # Step 1: Load data
    print("\n[DuckDB] Step 1: Loading Bronze / Silver / Gold data...")
    bronze_df, silver_df, gold_df = load_dataframes()

    # Steps 2 & 3: Evidently reports (or fallback)
    if EVIDENTLY_AVAILABLE:
        evidently_mode = "full"
        quality_summary = run_quality_report(silver_df)
        drift_summary   = run_drift_report(bronze_df, silver_df)
    else:
        evidently_mode  = "fallback"
        quality_summary, drift_summary = run_fallback_checks(bronze_df, silver_df, gold_df)

    # Step 4: Bedrock morning report
    morning_report_text, bedrock_usage = generate_morning_report(quality_summary, drift_summary, gold_df)

    # ── ACCOUNTABILITY GATE ───────────────────────────────────────────────────
    print()
    print("  Evidently flagged the issues above.")
    print("  → Pick the ONE finding you'd escalate to your manager first.")
    print("    Why is it the most critical? (1 sentence): ")
    student_judgment = input("  Your answer: ").strip()
    if not student_judgment:
        student_judgment = "NOT ANSWERED"

    # Step 5: Save combined report
    report_path = save_observability_report(
        quality_summary, drift_summary, morning_report_text,
        bedrock_usage, student_judgment, evidently_mode,
    )

    # ── Debrief ───────────────────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print("  DEBRIEF — What Just Happened")
    print("=" * 65)
    print()
    print("  WHAT JUST HAPPENED:")
    print("  Evidently AI profiled your Silver layer and compared it to")
    print("  Bronze — showing exactly where data quality degrades between")
    print("  pipeline stages. Nova Lite translated those numbers into the")
    print("  DataOps morning report your team reads every day at 08:00.")
    print("  This is the final observability layer: tests check correctness,")
    print("  SLOs define health, observability proves health in production.")
    print()
    print("  WHAT AI GOT RIGHT:")
    print("    1. Morning report structure — Status + Findings + Actions is")
    print("       exactly the format SRE teams use in incident runbooks")
    print("    2. Specific numbers — AI used actual metrics, not placeholders,")
    print("       because we passed the Evidently JSON as context")
    print("    3. Drift detection framing — AI correctly tied Bronze->Silver")
    print("       drift to the Silver transform rules, not random noise")
    print()
    print("  WHAT AI GETS WRONG (always check these):")
    print("    1. 'HEALTHY' verdict on a small dataset is almost always wrong.")
    print("       Evidently needs historical baselines to flag anomalies;")
    print("       with 21 rows, almost nothing looks statistically significant.")
    print("    2. AI's 'Recommended Actions' are generic — 'check the pipeline'")
    print("       is not actionable. Real actions name the table, the column,")
    print("       and the person responsible.")
    print("    3. Column drift on categorical columns (status, payment_method)")
    print("       may be flagged even when the change is expected (Silver FILTERS")
    print("       nulls — that is intentional drift, not a bug).")
    print()
    print("  THE RULE TO REMEMBER:")
    print("    Evidently tells you WHAT changed. Only you know whether the")
    print("    change is a bug or a feature of the transform.")
    print()
    print("  WHERE THIS FITS NEXT:")
    print("    Day 12: A self-heal agent reads this observability output and")
    print("    automatically opens a GitHub issue or patches the pipeline.")
    print(f"{'=' * 65}\n")

    print(f"  Files generated:")
    if evidently_mode == "full":
        print(f"    devops_brain/observability/silver_quality_report.html")
        print(f"    devops_brain/observability/bronze_silver_drift_report.html")
    else:
        print(f"    devops_brain/observability/fallback_quality_report.txt")
        print(f"    (HTML reports skipped — install evidently for full reports)")
    print(f"    devops_brain/observability/morning_report.md")
    print(f"    devops_brain/observability_report.json")
    print()
    print(f"  Next: python 6_competitive_build.py")


if __name__ == "__main__":
    main()
