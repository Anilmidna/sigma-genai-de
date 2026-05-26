"""
Schema Drift Handler — Day 7, Module 4 (Stretch Goal)
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
MISSION:
  At 03:47 UTC, the upstream payment team deployed a new version
  of their transaction API. Two new fields started appearing in
  the CSV: payment_gateway and discount_amount.

  The Sigma DataTech pipeline is already running. Nobody told
  the data engineering team about the change. The pipeline
  does not crash — but Bronze is now silently writing columns
  that Silver doesn't know about.

  This is schema drift. It's the most common silent pipeline
  killer in production. Today you simulate it, observe the
  problem, and use AI to generate an evolution handler.

MANUAL FIRST (do this BEFORE running the script):
  Look at SCHEMA_BRONZE in sample_data.py.
  Now imagine payment_gateway (string) and discount_amount (float)
  appear in the incoming CSV but not in SCHEMA_BRONZE.
  What should the pipeline do?
  a) Add them to the schema automatically
  b) Drop them silently
  c) Flag them as anomalies and alert
  d) Halt the pipeline
  Write your answer and reasoning. 2 minutes. THEN run.

STRETCH STUDENT TASK (at the bottom of this output):
  Add a 3rd drifted column 'refund_flag' (boolean) to the
  simulation, re-run, and observe how the handler responds.
  Does it recommend the correct action?

WHERE THIS FITS IN THE PLATFORM:
  Day 7 (today): understand schema drift patterns
  Day 11: Governance Agent auto-detects schema changes on
          new file arrivals and quarantines or escalates
  Day 12: Self-heal agent handles schema drift as one of
          its 3 repair scenarios

HOW TO RUN:
  cd repo/day7/lab
  python 4_stretch_goal_schema_drift.py
  (Can run standalone — does not require Modules 1-3)

OUTPUT:
  pipeline_brain/schema_drift_report.json      <- analysis + decision
  pipeline_brain/schema_evolution_handler.py   <- generated Python handler

IMPORTANT: This is the stretch goal. Core lab = Modules 1-3.
═══════════════════════════════════════════════════════════════
"""

import boto3
import json
import os
from datetime import datetime, timezone
from sample_data import SCHEMA_BRONZE, SCHEMA_SILVER

# ── CONFIGURATION ──────────────────────────────────────────────────────────
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
MODEL_ID = "amazon.nova-lite-v1:0"
OUTPUT_DIR = "pipeline_brain"

# ── SCHEMA DRIFT SIMULATION ────────────────────────────────────────────────
# These are the new columns that appeared in the upstream CSV without warning.
# In production this happens because: API version bump, upstream schema migration,
# new feature launch by another team, or a data provider changing their export format.
DRIFTED_COLUMNS = {
    "payment_gateway":  "string",    # new: which payment processor handled the txn
    "discount_amount":  "float",     # new: discount applied at checkout
}

# ── SYSTEM PROMPT ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a senior Data Engineer specialising in schema governance.
You analyse schema changes in data pipelines and recommend the safest evolution strategy.

For each new column you detect, you reason through:
1. Data type compatibility (can existing consumers handle this?)
2. Business impact (is this column load-bearing for any downstream query?)
3. Risk level (breaking change vs additive vs neutral)

You generate Python code that implements your recommended strategy.
Return clean Python code — no markdown fences, no prose explanations."""


def simulate_schema_drift() -> dict:
    """
    Create the 'drifted' schema by adding new columns to Bronze schema.
    This simulates what the incoming CSV would look like after an upstream change.
    """
    drifted_schema = {**SCHEMA_BRONZE, **DRIFTED_COLUMNS}
    return drifted_schema


def detect_drift(expected: dict, actual: dict) -> dict:
    """
    Compare expected vs actual schema to find new, removed, and changed columns.
    """
    expected_cols = set(expected.keys())
    actual_cols = set(actual.keys())

    new_columns    = {k: actual[k] for k in (actual_cols - expected_cols)}
    removed_columns = {k: expected[k] for k in (expected_cols - actual_cols)}
    type_changes   = {
        k: {"expected": expected[k], "actual": actual[k]}
        for k in (expected_cols & actual_cols)
        if expected[k] != actual[k]
    }

    return {
        "new_columns":     new_columns,
        "removed_columns": removed_columns,
        "type_changes":    type_changes,
        "has_drift":       bool(new_columns or removed_columns or type_changes),
    }


def generate_evolution_handler(
    original_schema: dict,
    drifted_schema:  dict,
    drift_analysis:  dict,
) -> tuple[str, dict]:
    """
    Ask Bedrock to generate a schema evolution handler for the detected drift.
    Returns (handler_code, usage_dict).
    """
    user_prompt = f"""You detected schema drift in a production data pipeline.

EXPECTED SCHEMA (what the pipeline was built for):
{json.dumps(original_schema, indent=2)}

ACTUAL SCHEMA (what arrived in today's CSV):
{json.dumps(drifted_schema, indent=2)}

DRIFT ANALYSIS:
{json.dumps(drift_analysis, indent=2)}

Generate a Python schema_evolution_handler module that:

1. DETECT function: detect_schema_drift(expected_schema: dict, actual_schema: dict) -> dict
   - Returns: {{new_columns, removed_columns, type_changes, drift_severity: 'NONE'|'LOW'|'HIGH'|'BREAKING'}}
   - LOW = new nullable columns only (additive, safe to add)
   - HIGH = new non-nullable columns or type changes (may break consumers)
   - BREAKING = removed columns or type narrowing (will break consumers)

2. DECIDE function: decide_action(drift_report: dict) -> dict
   - For each new column: decide ADD_TO_SCHEMA, DROP_SILENTLY, or FLAG_ANOMALY
   - Rules:
     * New string column (nullable): ADD_TO_SCHEMA
     * New float/numeric (could affect revenue calculations): FLAG_ANOMALY first, then add
     * Removed column: HALT (never silently drop — downstream queries will break)
     * Type widening (e.g., int->float): ADD_TO_SCHEMA with note
     * Type narrowing (e.g., float->int): FLAG_ANOMALY
   - Returns: {{column_name: {{action, reason, risk_level}}}}

3. APPLY function: apply_schema_evolution(spark_df, decisions: dict, updated_schema: dict)
   - If action is DROP_SILENTLY: drop the column from the DataFrame
   - If action is ADD_TO_SCHEMA: keep it, add to schema registry
   - If action is FLAG_ANOMALY: keep the column but add a metadata flag column
   - Returns the evolved DataFrame + a migration_notes list

4. MAIN function: handle_drift(expected_schema, actual_schema, spark_df=None)
   - Calls detect -> decide -> apply (if spark_df provided)
   - Prints a human-readable drift report
   - Returns the full evolution report dict

Include proper type hints and docstrings. Assume PySpark is available."""

    print(f"\n[Bedrock] Generating schema evolution handler...")
    print(f"[Bedrock] Model: {MODEL_ID}")
    print(f"[Bedrock] New columns to handle: {list(drift_analysis['new_columns'].keys())}")

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"maxTokens": 4000, "temperature": 0.3},
    )

    raw_text = response["output"]["message"]["content"][0]["text"]
    usage = response["usage"]
    print(f"[Bedrock] Handler generated. Tokens: {usage['inputTokens']} in / {usage['outputTokens']} out")

    # Strip markdown fences
    code = raw_text.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:])
        if code.rstrip().endswith("```"):
            code = code.rstrip()[:-3]

    return code, usage


def main():
    # ── MANUAL FIRST REMINDER ──────────────────────────────────
    print("\n" + "=" * 65)
    print("  MANUAL FIRST — Do This Before Running!")
    print("=" * 65)
    print("  Look at SCHEMA_BRONZE in sample_data.py.")
    print("  Two new columns will appear: payment_gateway (string)")
    print("  and discount_amount (float).")
    print()
    print("  What should the pipeline do?")
    print("    a) Add them to the schema automatically")
    print("    b) Drop them silently")
    print("    c) Flag as anomalies and alert")
    print("    d) Halt the pipeline")
    print()
    print("  Write your answer + reasoning. 2 minutes.")
    print("=" * 65)
    input("  [Press Enter when you have your answer] ")

    print("\n" + "=" * 65)
    print("  MODULE 4 (STRETCH): Schema Drift Handler")
    print("  Sigma Intelligence Platform | Day 7")
    print("=" * 65)

    # Step 1: Simulate the drift
    print("\n[Step 1] Simulating schema drift...")
    drifted_schema = simulate_schema_drift()
    print(f"  Original schema: {len(SCHEMA_BRONZE)} columns")
    print(f"  Drifted schema:  {len(drifted_schema)} columns")
    for col_name, col_type in DRIFTED_COLUMNS.items():
        print(f"  NEW: {col_name} ({col_type}) -- appeared without warning")

    # Step 2: Detect the drift
    print("\n[Step 2] Running drift detection...")
    drift_analysis = detect_drift(SCHEMA_BRONZE, drifted_schema)
    print(f"  Drift detected: {drift_analysis['has_drift']}")
    print(f"  New columns: {list(drift_analysis['new_columns'].keys())}")
    print(f"  Removed columns: {list(drift_analysis['removed_columns'].keys())}")
    print(f"  Type changes: {drift_analysis['type_changes']}")

    # Step 3: Generate the AI handler
    handler_code, usage = generate_evolution_handler(
        SCHEMA_BRONZE, drifted_schema, drift_analysis
    )

    # Step 4: Save outputs
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Save the handler code
    handler_path = os.path.join(OUTPUT_DIR, "schema_evolution_handler.py")
    with open(handler_path, "w", encoding="utf-8") as f:
        f.write(handler_code)
    print(f"\n[Output] Saved {handler_path}")

    # Save the drift report
    report = {
        "simulation": {
            "drifted_columns_injected": DRIFTED_COLUMNS,
            "description": "payment_gateway and discount_amount appeared in upstream CSV",
        },
        "original_schema": SCHEMA_BRONZE,
        "drifted_schema":  drifted_schema,
        "new_columns_detected": list(drift_analysis["new_columns"].keys()),
        "removed_columns_detected": list(drift_analysis["removed_columns"].keys()),
        "type_changes_detected": drift_analysis["type_changes"],
        "action_taken": "AI-generated schema evolution handler — see schema_evolution_handler.py",
        "updated_schema": drifted_schema,
        "model_used": MODEL_ID,
        "tokens_in": usage["inputTokens"],
        "tokens_out": usage["outputTokens"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    report_path = os.path.join(OUTPUT_DIR, "schema_drift_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[Output] Saved {report_path}")

    # ── DEBRIEF ────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print("  DEBRIEF — What Just Happened")
    print("=" * 65)
    print()
    print("  WHAT AI GOT RIGHT:")
    print("    1. Decision logic structure — detect/decide/apply is the")
    print("       correct separation of concerns for schema governance")
    print("    2. Severity classification — LOW/HIGH/BREAKING maps to")
    print("       real-world governance tiers (monitor / alert / halt)")
    print("    3. Type awareness — AI correctly flags discount_amount (float)")
    print("       as higher risk than payment_gateway (string), because")
    print("       float columns can affect revenue calculations")
    print()
    print("  WHAT AI GETS WRONG (always check these):")
    print("    1. 'DROP_SILENTLY' recommendation — AI may suggest dropping")
    print("       unknown columns. For financial data: NEVER drop silently.")
    print("       You need an audit trail of what was received.")
    print("    2. Missing the downstream impact check — AI decides per-column,")
    print("       but doesn't check: is this column referenced in Gold queries?")
    print("    3. Schema registry — AI writes to a local dict. Production")
    print("       schemas live in AWS Glue Catalog or Confluent Schema Registry.")
    print()
    print("  THE RULE TO REMEMBER:")
    print("    Schema drift is not a bug — it's an expected event in any")
    print("    real pipeline. The pipeline that crashes on schema change is")
    print("    worse than the one that flags and continues. Design for drift.")
    print()
    print("  WHERE THIS FITS NEXT:")
    print("    Day 11: Governance Agent handles schema drift as part of")
    print("    automated data intake. It uses the same detect/decide/apply")
    print("    pattern you just generated — but triggered by S3 file arrival.")
    print(f"{'=' * 65}")
    print()
    print("  ─── YOUR TURN (Student Task) ─────────────────────────────")
    print()
    print("  1. Open 4_stretch_goal_schema_drift.py (this file)")
    print("  2. Add a 3rd column to DRIFTED_COLUMNS (around line 71 in this file):")
    print('        "refund_flag": "boolean"')
    print("  3. Re-run: python 4_stretch_goal_schema_drift.py")
    print("  4. Observe: does the handler recommend the right action?")
    print("     (Hint: boolean on a financial record — is that low risk or high risk?)")
    print("  5. Bonus: what if refund_flag appeared in SCHEMA_SILVER too?")
    print("     Would the action change?")
    print()


if __name__ == "__main__":
    main()
