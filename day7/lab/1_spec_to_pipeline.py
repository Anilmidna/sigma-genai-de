"""
Spec-to-Pipeline Generator — Day 7, Module 1
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
MISSION:
  The data engineering team wrote a 1-page pipeline spec.
  Your job: use AI to turn that plain-English spec into
  production-grade PySpark code — the way senior DEs at
  top-tier companies actually work.

  Sigma DataTech processes 50,000 transactions per day.
  The analytics team needs Bronze -> Silver -> Gold tables
  ready by 04:00 UTC for the morning dashboard run.
  Today you generate that pipeline in under 2 minutes.

MANUAL FIRST (do this BEFORE running the script):
  Read the PIPELINE_SPEC imported from sample_data.py.
  Take 2 minutes: write down the 3 PySpark transformations
  you would need for the Silver layer.
  (Hint: think about cast, filter, join — in what order and why?)
  THEN run the script and see what AI produces.

WHERE THIS FITS IN THE PLATFORM:
  Day 7 (today): AI generates the pipeline scaffold
  Day 8 (tomorrow): AI generates tests for this exact code
  Day 12: A self-heal agent detects failures in this pipeline
           and fixes them automatically

HOW TO RUN:
  cd repo/day7/lab
  python 1_spec_to_pipeline.py

OUTPUT:
  pipeline_brain/generated_pipeline.py   <- the PySpark code
  pipeline_brain/generation_report.json  <- model metadata

IMPORTANT: SPEND 5 MINUTES READING THIS FILE. YOU HAVE A QUIZ ON IT.
═══════════════════════════════════════════════════════════════
"""

import boto3
import json
import os
from datetime import datetime, timezone
from sample_data import PIPELINE_SPEC as _SAMPLE_SPEC

# ── SPEC SOURCE DETECTION ──────────────────────────────────────────────────
# If the student saved their team spec as my_pipeline_spec.txt, use that.
# Otherwise fall back to the sample spec with a clear info message.
_SPEC_FILE = os.path.join(os.path.dirname(__file__), "my_pipeline_spec.txt")
if os.path.exists(_SPEC_FILE):
    with open(_SPEC_FILE, "r", encoding="utf-8") as _f:
        PIPELINE_SPEC = _f.read()
    print(f"[INFO] Loaded spec from lab/my_pipeline_spec.txt ({len(PIPELINE_SPEC)} chars)")
else:
    PIPELINE_SPEC = _SAMPLE_SPEC
    print("[INFO] No my_pipeline_spec.txt found. Using sample PIPELINE_SPEC.")
    print("       To use your team's spec: save it as lab/my_pipeline_spec.txt and re-run.")

# ── CONFIGURATION ──────────────────────────────────────────────────────────
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
MODEL_ID = "amazon.nova-lite-v1:0"     # Nova Lite handles scaffolding well
OUTPUT_DIR = "pipeline_brain"

# ── SYSTEM PROMPT ──────────────────────────────────────────────────────────
# Two things matter most in this prompt:
#   1. Role (senior PySpark engineer — sets vocabulary and idiom expectations)
#   2. Forced structure (section headers, function names) — gives us parseable code
SYSTEM_PROMPT = """You are a senior PySpark Data Engineer at a fintech company.
You write production-grade PySpark code that runs on AWS EMR.
When given a pipeline specification, you generate complete, runnable Python files.

Your code must:
- Use SparkSession.builder.appName(...).getOrCreate()
- Define one function per pipeline stage (e.g., ingest_bronze, transform_silver, build_gold)
- Include proper type imports from pyspark.sql.types and pyspark.sql.functions
- Use descriptive variable names matching the spec domain (transactions, merchants)
- Add inline comments explaining non-obvious logic
- Handle the business rules exactly as specified

Return ONLY Python code. No markdown fences. No explanations before or after the code."""


def generate_bronze_silver(spec: str) -> tuple[str, dict]:
    """
    Phase 1: Generate Bronze and Silver layer code from the spec.
    Returns (code_text, usage_dict).
    """
    user_prompt = f"""Generate PySpark code for the BRONZE and SILVER layers of this pipeline.

PIPELINE SPEC:
{spec}

Generate:
1. A function ingest_bronze(spark, input_path, output_path, run_date, run_id) that:
   - Reads CSV with all columns as strings
   - Adds ingestion_timestamp, source_file, pipeline_run_id columns
   - Writes Parquet partitioned by date

2. A function transform_silver(spark, bronze_path, merchants_path, output_path, run_date) that:
   - Reads Bronze Parquet with partition pruning on run_date
   - Casts columns to correct types (amount->float, transaction_date->date, IDs->string)
   - Filters NULL transaction_id and negative amounts
   - Deduplicates on transaction_id keeping latest ingestion_timestamp
   - Joins with merchants (broadcast hint, cache merchants)
   - Adds quality_flag column (CLEAN or UNMATCHED)
   - Writes Parquet partitioned by date

Include all imports at the top. Include a main() function that calls both stages."""

    print(f"\n[Bedrock] Phase 1: Generating Bronze + Silver layers...")
    print(f"[Bedrock] Model: {MODEL_ID} | Spec length: {len(spec)} chars")

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"maxTokens": 4000, "temperature": 0.3},
    )

    raw_text = response["output"]["message"]["content"][0]["text"]
    usage = response["usage"]
    print(f"[Bedrock] Phase 1 complete. Tokens: {usage['inputTokens']} in / {usage['outputTokens']} out")

    # Strip markdown fences if AI added them
    code = raw_text.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:])          # remove first fence line
        if code.rstrip().endswith("```"):
            code = code.rstrip()[:-3]        # remove closing fence

    return code, usage


def generate_gold(spec: str) -> tuple[str, dict]:
    """
    Phase 2: Generate Gold layer aggregations.
    Splitting into two phases avoids token limit issues with large specs.
    Returns (code_text, usage_dict).
    """
    user_prompt = f"""Generate PySpark code for the GOLD layer of this pipeline.
Assume Bronze and Silver layers are already written. Add to the same file.

PIPELINE SPEC (Gold section):
{spec}

Generate THREE functions:
1. build_merchant_performance(spark, silver_path, output_path, run_date)
   - merchant_id, merchant_name, category, city, date
   - total_revenue: SUM(amount) WHERE status='COMPLETED'
   - txn_count: COUNT(*)
   - failure_rate_pct: COUNT(FAILED)/COUNT(*)*100
   - Partitioned by date

2. build_customer_ltv(spark, silver_path, output_path)
   - customer_id, total_spent (COMPLETED only), total_txns
   - avg_txn_value, first_txn_date, last_txn_date
   - preferred_payment_method (mode — most frequent)
   - NOT partitioned (one row per customer, cumulative)

3. build_daily_summary(spark, silver_path, output_path, run_date)
   - date, total_revenue, total_txns, unique_customers
   - unique_merchants, failure_rate_pct
   - Partitioned by date

Also include a run_gold(spark, silver_path, gold_output_dir, run_date) function
that calls all three and writes a run_metadata dict to JSON."""

    print(f"\n[Bedrock] Phase 2: Generating Gold aggregations...")

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"maxTokens": 4000, "temperature": 0.3},
    )

    raw_text = response["output"]["message"]["content"][0]["text"]
    usage = response["usage"]
    print(f"[Bedrock] Phase 2 complete. Tokens: {usage['inputTokens']} in / {usage['outputTokens']} out")

    code = raw_text.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:])
        if code.rstrip().endswith("```"):
            code = code.rstrip()[:-3]

    return code, usage


def save_pipeline(bronze_silver_code: str, gold_code: str) -> str:
    """Combine both phases into one well-structured pipeline file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "generated_pipeline.py")

    header = f'''"""
Sigma DataTech Transaction Analytics Pipeline
AI-Generated by Module 1 | Day 7 — Pipeline Brain
Generated: {datetime.now(timezone.utc).isoformat()}

This file was produced by 1_spec_to_pipeline.py from a plain-English spec.
It is a FIRST DRAFT — review before running against production data.

Architecture: Bronze -> Silver -> Gold (medallion pattern)
"""

# ═══════════════════════════════════════════════════════════════
# SECTION 1: BRONZE + SILVER LAYERS
# ═══════════════════════════════════════════════════════════════
'''

    separator = '''

# ═══════════════════════════════════════════════════════════════
# SECTION 2: GOLD AGGREGATION LAYER
# ═══════════════════════════════════════════════════════════════
'''

    full_code = header + bronze_silver_code + separator + gold_code

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_code)

    return output_path


def main():
    # ── MANUAL FIRST REMINDER ──────────────────────────────────
    print("\n" + "=" * 65)
    print("  MANUAL FIRST — Do This Before Running!")
    print("=" * 65)
    if os.path.exists(_SPEC_FILE):
        print("  You are using YOUR team's spec (lab/my_pipeline_spec.txt).")
    else:
        print("  You are using the sample spec from sample_data.py.")
    print("  Read the spec now. Write down: what 3 PySpark transformations")
    print("  would you need for the Silver layer?")
    print("  (Think: cast, filter, join, dedup — in what order and why?)")
    print("  Take 2 minutes. Then come back and press Enter to continue.")
    print("=" * 65)
    input("  [Press Enter when you're ready to see what AI generates] ")

    print("\n" + "=" * 65)
    print("  MODULE 1: Spec-to-Pipeline Generator")
    print("  Sigma Intelligence Platform | Day 7")
    print("=" * 65)
    print(f"  Spec characters: {len(PIPELINE_SPEC)}")
    print(f"  Strategy: Two-phase generation (Bronze+Silver, then Gold)")
    print(f"  Reason: Splitting avoids token limits and keeps each prompt focused")

    # Phase 1: Bronze + Silver
    bs_code, bs_usage = generate_bronze_silver(PIPELINE_SPEC)

    # Phase 2: Gold
    gold_code, gold_usage = generate_gold(PIPELINE_SPEC)

    # Save combined file
    output_path = save_pipeline(bs_code, gold_code)
    file_size = os.path.getsize(output_path)

    # Save generation report
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report = {
        "model": MODEL_ID,
        "strategy": "two_phase",
        "spec_chars": len(PIPELINE_SPEC),
        "bronze_silver_tokens": {
            "input": bs_usage["inputTokens"],
            "output": bs_usage["outputTokens"],
        },
        "gold_tokens": {
            "input": gold_usage["inputTokens"],
            "output": gold_usage["outputTokens"],
        },
        "total_tokens_in":  bs_usage["inputTokens"] + gold_usage["inputTokens"],
        "total_tokens_out": bs_usage["outputTokens"] + gold_usage["outputTokens"],
        "output_file": output_path,
        "output_bytes": file_size,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    report_path = os.path.join(OUTPUT_DIR, "generation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    # ── DEBRIEF ────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print("  DEBRIEF — What Just Happened")
    print("=" * 65)
    print(f"\n  What was generated:")
    print(f"    pipeline_brain/generated_pipeline.py  ({file_size:,} bytes)")
    print(f"    pipeline_brain/generation_report.json")
    print(f"\n  Two-phase generation stats:")
    print(f"    Phase 1 (Bronze+Silver): {bs_usage['outputTokens']} tokens out")
    print(f"    Phase 2 (Gold):          {gold_usage['outputTokens']} tokens out")
    print(f"    Total input tokens:      {report['total_tokens_in']:,}")
    print()
    print("  WHAT AI GOT RIGHT:")
    print("    1. PySpark imports and SparkSession setup — muscle memory for Nova")
    print("    2. Function structure per stage — matches the spec exactly")
    print("    3. Medallion architecture pattern — heavily represented in training data")
    print()
    print("  WHAT AI GETS WRONG (always check these):")
    print("    1. Broadcast hints — AI writes broadcast(merchants_df) but wrong syntax")
    print("       Real: spark.range(1).hint('broadcast') — check the actual Spark API")
    print("    2. Hardcoded paths — AI uses '/data/bronze/' but yours is different")
    print("       Fix: always parameterise paths, never hardcode")
    print("    3. Missing idempotency — AI uses .mode('append') instead of")
    print("       delete-partition-then-overwrite. Module 3 fixes this.")
    print()
    print("  THE RULE TO REMEMBER:")
    print("    AI generates the scaffold in 60 seconds. You spend 30 minutes")
    print("    reviewing it. That's still 10x faster than writing from scratch.")
    print()
    print("  WHERE THIS FITS NEXT:")
    print("    Tomorrow (Day 8): AI generates a full pytest suite for this file.")
    print("    Every function AI wrote today becomes a test target tomorrow.")
    print(f"{'=' * 65}\n")

    print(f"  Next: open pipeline_brain/generated_pipeline.py and read it.")
    print(f"  Find ONE thing AI got wrong before Module 3 hardening.\n")


if __name__ == "__main__":
    main()
