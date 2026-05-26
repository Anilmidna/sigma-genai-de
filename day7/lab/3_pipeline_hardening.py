"""
Pipeline Hardening — Day 7, Module 3
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
MISSION:
  The pipeline AI generated in Module 1 is a good scaffold —
  but it would crash silently in production. No try/except.
  No idempotency. No row count logging. No run metadata.

  Sigma DataTech's SRE team has a rule: any pipeline that
  touches financial data must meet 5 hardening criteria
  before it can be merged to main. Today you use AI to add
  all 5 in one pass — then review what it produced.

  This module uses Nova PRO (not Lite) because hardening
  requires reasoning about code structure, not just scaffolding.

MANUAL FIRST (do this BEFORE running the script):
  Open pipeline_brain/generated_pipeline.py (from Module 1).
  Find ONE place where this pipeline would fail silently
  — no error message, no log, just wrong/missing output.
  Write it down. Take 2 minutes.
  THEN run this script and see if AI finds the same thing.

WHERE THIS FITS IN THE PLATFORM:
  Day 7 (today): AI adds production safety patterns
  Day 8 (tomorrow): pytest tests will target hardened_pipeline.py
  Day 12: Self-heal agent reads run_metadata.json to detect
           anomalies (row count drops, stage failures)

HOW TO RUN:
  cd repo/day7/lab
  python 3_pipeline_hardening.py
  (Run AFTER Module 1 — reads pipeline_brain/generated_pipeline.py)

OUTPUT:
  pipeline_brain/hardened_pipeline.py     <- production-ready code
  pipeline_brain/hardening_report.json    <- what was added + line counts

IMPORTANT: SPEND 5 MINUTES READING THIS FILE. YOU HAVE A QUIZ ON IT.
═══════════════════════════════════════════════════════════════
"""

import boto3
import json
import os
from datetime import datetime, timezone
from sample_data import PIPELINE_SPEC

# ── CONFIGURATION ──────────────────────────────────────────────────────────
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

# Nova PRO for hardening — this requires structural reasoning, not just scaffolding.
# Nova Lite would miss subtleties like WHERE idempotency needs to happen vs WHERE
# a try/except would swallow legitimate errors.
MODEL_ID = "amazon.nova-pro-v1:0"
OUTPUT_DIR = "pipeline_brain"

# ── STUB CODE (fallback if Module 1 hasn't been run yet) ──────────────────
# This is intentionally brittle — it's meant to have the same problems
# that the AI-generated code has, so hardening still demonstrates value.
STUB_PIPELINE = '''"""
Sigma DataTech Transaction Analytics Pipeline — Stub
(Run 1_spec_to_pipeline.py first to generate the real version)
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, current_timestamp
from pyspark.sql.types import FloatType, StringType, DateType

def ingest_bronze(spark, input_path, output_path, run_date, run_id):
    df = spark.read.option("header", True).csv(input_path)
    df = df.withColumn("ingestion_timestamp", current_timestamp())
    df = df.withColumn("source_file", lit(input_path))
    df = df.withColumn("pipeline_run_id", lit(run_id))
    df.write.mode("overwrite").partitionBy("transaction_date").parquet(output_path)

def transform_silver(spark, bronze_path, merchants_path, output_path, run_date):
    df = spark.read.parquet(bronze_path)
    merchants = spark.read.parquet(merchants_path)
    df = df.withColumn("amount", col("amount").cast(FloatType()))
    df = df.withColumn("transaction_date", col("transaction_date").cast(DateType()))
    df = df.filter(col("transaction_id").isNotNull())
    df = df.filter(col("amount") >= 0)
    df = df.join(merchants, "merchant_id", "left")
    df.write.mode("append").partitionBy("transaction_date").parquet(output_path)

def build_gold(spark, silver_path, output_path, run_date):
    df = spark.read.parquet(silver_path)
    result = df.groupBy("merchant_id", "transaction_date").sum("amount")
    result.write.mode("append").partitionBy("transaction_date").parquet(output_path)

def main():
    spark = SparkSession.builder.appName("SigmaPipeline").getOrCreate()
    run_id = "manual_run"
    run_date = "2024-01-15"
    ingest_bronze(spark, "data/transactions.csv", "data/bronze", run_date, run_id)
    transform_silver(spark, "data/bronze", "data/merchants", "data/silver", run_date)
    build_gold(spark, "data/silver", "data/gold", run_date)

if __name__ == "__main__":
    main()
'''

# ── SYSTEM PROMPT ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a principal Data Engineer performing a production-readiness review.
You take PySpark pipeline code and harden it to meet enterprise standards.

You are precise: you add error handling in the RIGHT places (not everywhere),
you implement idempotency correctly (delete-partition-then-write, not just mode=overwrite),
and you add logging that gives operators enough signal to debug without noise.

Return ONLY the complete hardened Python file. No markdown fences. No commentary."""


def load_generated_pipeline() -> tuple[str, str]:
    """
    Load the pipeline from Module 1 output, or fall back to stub.
    Returns (code, source_label).
    """
    generated_path = os.path.join(OUTPUT_DIR, "generated_pipeline.py")
    if os.path.exists(generated_path):
        with open(generated_path, "r", encoding="utf-8") as f:
            code = f.read()
        print(f"[Load] Using AI-generated pipeline from Module 1")
        print(f"[Load] {generated_path} ({len(code):,} chars, {len(code.splitlines())} lines)")
        return code, "pipeline_brain/generated_pipeline.py"
    else:
        print(f"[Load] Module 1 output not found. Using embedded stub.")
        print(f"[Load] (Run 1_spec_to_pipeline.py first for better results)")
        return STUB_PIPELINE, "embedded_stub"


def harden_pipeline(code: str, spec: str) -> tuple[str, dict]:
    """
    Send pipeline code to Nova Pro with hardening requirements.
    Returns (hardened_code, usage_dict).
    """
    user_prompt = f"""Harden this PySpark pipeline to meet production standards.

ORIGINAL PIPELINE CODE:
{code}

PIPELINE SPEC CONTEXT (for business rules):
{spec[:2000]}

Add ALL FIVE of these improvements:

1. TRY/EXCEPT ERROR HANDLING
   - Wrap each stage function body in try/except
   - On exception: log the stage name, error message, and row count at time of failure
   - Re-raise the exception (do not swallow it — fail fast is correct for financial data)
   - Use logging module (not print) for error messages

2. IDEMPOTENCY — Delete-Partition-Then-Write Pattern
   - Before writing any Parquet partition: delete the existing partition path first
   - Use shutil.rmtree(partition_path, ignore_errors=True) to clear it
   - THEN write with mode("overwrite")
   - This is the correct pattern — never use mode("append") for daily partitions
   - Add a comment explaining WHY this is idempotent

3. PARTITION PRUNING ON ALL READS
   - Add .filter(col("transaction_date") == run_date) BEFORE any joins or aggregations
   - This prevents full-table scans when reading partitioned data
   - Add a comment: "Partition pruning — only read today's data, not full history"

4. ROW COUNT LOGGING AT EACH STAGE
   - After each major transformation, call df.count() and log the result
   - Log format: "[Stage: {stage_name}] {label}: {count:,} rows"
   - Track these counts: input_count, after_filter_count, after_dedup_count, output_count

5. RUN METADATA JSON
   - At the end of the pipeline, collect all row counts into a dict
   - Add: pipeline_name, run_date, run_id, run_status ('SUCCESS' or 'FAILED'), error_message
   - Add: started_at, completed_at (ISO format timestamps)
   - Save to run_metadata_{{run_date}}.json in the output directory
   - This file is read by the Day 12 self-heal agent to detect anomalies

Return the COMPLETE hardened file with all 5 improvements added."""

    print(f"\n[Bedrock] Sending pipeline for hardening...")
    print(f"[Bedrock] Model: {MODEL_ID} (Nova Pro — structural reasoning required)")
    print(f"[Bedrock] Input code: {len(code.splitlines())} lines")

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"maxTokens": 4000, "temperature": 0.2},
    )

    raw_text = response["output"]["message"]["content"][0]["text"]
    usage = response["usage"]
    print(f"[Bedrock] Hardening complete. Tokens: {usage['inputTokens']} in / {usage['outputTokens']} out")

    # Strip markdown fences
    hardened = raw_text.strip()
    if hardened.startswith("```"):
        lines = hardened.split("\n")
        hardened = "\n".join(lines[1:])
        if hardened.rstrip().endswith("```"):
            hardened = hardened.rstrip()[:-3]

    return hardened, usage


def analyse_improvements(original: str, hardened: str) -> list[str]:
    """
    Detect which improvements were actually added by comparing code.
    Returns list of improvement descriptions.
    """
    improvements = []

    if "try:" in hardened and "except" in hardened:
        improvements.append("try/except error handling added around pipeline stages")

    if "shutil.rmtree" in hardened or "delete_partition" in hardened or "rmtree" in hardened:
        improvements.append("idempotency: delete-partition-then-write pattern added")
    elif hardened.count('mode("overwrite")') > original.count('mode("overwrite")'):
        improvements.append("idempotency: overwrite mode enforced on all writes")

    if ".count()" in hardened and ".count()" not in original:
        improvements.append("row count logging added at each pipeline stage")
    elif hardened.count(".count()") > original.count(".count()"):
        improvements.append("row count logging expanded to cover all stages")

    if "run_metadata" in hardened and "run_metadata" not in original:
        improvements.append("run_metadata JSON written at pipeline completion")

    if "logging" in hardened and "logging" not in original:
        improvements.append("Python logging module added (replaces print statements)")

    if "partition_prune" in hardened or ("transaction_date" in hardened and ".filter" in hardened):
        improvements.append("partition pruning filter added to Parquet reads")

    if not improvements:
        improvements.append("hardening applied — review hardened_pipeline.py for details")

    return improvements


def main():
    # ── MANUAL FIRST REMINDER ──────────────────────────────────
    print("\n" + "=" * 65)
    print("  MANUAL FIRST — Do This Before Running!")
    print("=" * 65)
    print("  Open pipeline_brain/generated_pipeline.py")
    print("  Find ONE place where this pipeline would fail silently")
    print("  (no crash, no error, just missing or wrong output).")
    print("  Hint: look at how partitions are written.")
    print("  Take 2 minutes. Write it down.")
    print("=" * 65)
    input("  [Press Enter when you have your answer] ")

    print("\n" + "=" * 65)
    print("  MODULE 3: Pipeline Hardening")
    print("  Sigma Intelligence Platform | Day 7")
    print("=" * 65)

    # Load source pipeline
    original_code, source = load_generated_pipeline()
    original_lines = len(original_code.splitlines())

    # Harden it
    hardened_code, usage = harden_pipeline(original_code, PIPELINE_SPEC)
    hardened_lines = len(hardened_code.splitlines())

    # Analyse improvements
    improvements = analyse_improvements(original_code, hardened_code)

    # Save hardened pipeline
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    hardened_path = os.path.join(OUTPUT_DIR, "hardened_pipeline.py")
    with open(hardened_path, "w", encoding="utf-8") as f:
        f.write(hardened_code)
    hardened_size = os.path.getsize(hardened_path)
    print(f"\n[Output] Saved {hardened_path} ({hardened_size:,} bytes)")

    # Save hardening report
    report = {
        "source_file":      source,
        "model_used":       MODEL_ID,
        "original_lines":   original_lines,
        "hardened_lines":   hardened_lines,
        "lines_added":      hardened_lines - original_lines,
        "improvements_added": improvements,
        "tokens_in":        usage["inputTokens"],
        "tokens_out":       usage["outputTokens"],
        "generated_at":     datetime.now(timezone.utc).isoformat(),
    }

    report_path = os.path.join(OUTPUT_DIR, "hardening_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[Output] Saved {report_path}")

    # ── DEBRIEF ────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print("  DEBRIEF — What Just Happened")
    print("=" * 65)
    print(f"\n  Before hardening: {original_lines} lines")
    print(f"  After hardening:  {hardened_lines} lines")
    print(f"  Added:            {hardened_lines - original_lines} lines")
    print()
    print("  IMPROVEMENTS DETECTED:")
    for imp in improvements:
        print(f"    + {imp}")
    print()
    print("  WHAT AI GOT RIGHT:")
    print("    1. Error handling placement — AI correctly wraps stage boundaries,")
    print("       not every single line (which would hide root causes)")
    print("    2. Run metadata structure — AI creates a dict that a monitoring")
    print("       system can parse. This is exactly what Day 12 self-heal reads.")
    print("    3. Row count logging — AI logs at the right checkpoints: input,")
    print("       after filter, after dedup, output. Four numbers tell the full story.")
    print()
    print("  WHAT AI GETS WRONG (always check these):")
    print("    1. Idempotency implementation — AI may use mode('overwrite') which")
    print("       overwrites the WHOLE table, not just one partition.")
    print("       Correct: shutil.rmtree(partition_path) THEN write.")
    print("       Wrong: .write.mode('overwrite').parquet(base_path)")
    print("    2. Exception swallowing — AI sometimes adds bare 'except Exception: pass'")
    print("       For financial data: ALWAYS re-raise. Never swallow.")
    print("    3. Missing the 5% quality gate — the spec says halt if >5% fail checks.")
    print("       AI adds try/except but may not add the percentage threshold check.")
    print()
    print("  THE RULE TO REMEMBER:")
    print("    Hardening is where AI adds the MOST value — it knows all the patterns.")
    print("    But idempotency is the hardest DE concept: AI gets the keyword right,")
    print("    not always the implementation. Read the diff, don't just trust line counts.")
    print()
    print("  WHERE THIS FITS NEXT:")
    print("    Tomorrow (Day 8): pytest tests will be generated for hardened_pipeline.py.")
    print("    Day 12: The self-heal agent reads run_metadata.json to detect")
    print("    anomalies (e.g., row count dropped 90% — was that expected?).")
    print(f"{'=' * 65}")
    print()
    print("  Next: diff generated_pipeline.py vs hardened_pipeline.py")
    print("  Question: did AI implement idempotency correctly?")
    print()


if __name__ == "__main__":
    main()
