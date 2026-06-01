"""
==============================================================================
DAY 11 — LAB 4 (STRETCH GOAL): SELF-HEAL LOOP AGENT
Detect → Diagnose → Fix → Re-run → Alert
==============================================================================

MISSION BRIEFING
----------------
It's 2 AM. The ingestion pipeline fails. The on-call DE gets paged.
The logs say: "NullPointerException in amount field."

At Sigma DataTech, this happens 3x per week. Each incident costs 45 minutes
of on-call time. The CTO says: "Build an agent that fixes itself."

The self-heal loop:
  1. DETECT  — monitor pipeline output for failure signals
  2. DIAGNOSE — LLM reads the error + data context, classifies root cause
  3. FIX     — apply the appropriate automated remediation
  4. RE-RUN  — execute the pipeline again with the fix applied
  5. ALERT   — generate incident report regardless of outcome

This is a STRETCH GOAL. You will write parts of this yourself.
The scaffold is here. You complete the TODO sections.

WHAT YOU WILL LEARN
-------------------
- Self-healing agent loop architecture
- Root cause classification using LLMs
- Automated remediation patterns (which fixes are safe to automate)
- Incident report generation for audit trails
- When to stop the loop (max retry + escalation to human)

MANUAL FIRST (3 minutes)
-------------------------
Write down 5 common data pipeline failures at Sigma DataTech.
For each: Can it be auto-fixed? What is the safe fix action?
Then compare with how this script classifies them.

WHERE THIS FITS
---------------
This is the "brain" of production-grade data reliability engineering.
Day 12 capstone Option B requires a self-healing agent — this is the template.

==============================================================================
OUTPUT
------
  agent_outputs/self_heal_incident_report.json  — full incident audit trail
==============================================================================
"""

import os, sys, json, time
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import boto3
    import pandas as pd
except ImportError as e:
    print(f"[ERROR] {e}. Run: pip install boto3 pandas")
    sys.exit(1)

DATA_DIR   = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "agent_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MODEL_ID = "amazon.nova-pro-v1:0"
REGION   = "us-east-1"
MAX_HEAL_ATTEMPTS = 3   # safety cap — never loop infinitely

# ── Bedrock helper ────────────────────────────────────────────────────────────
def call_bedrock(prompt: str, max_tokens: int = 800) -> str:
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.1},
    }
    resp = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    return json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"].strip()

# ─────────────────────────────────────────────────────────────────────────────
# SIMULATED PIPELINE FAILURES
# In production these would come from real pipeline logs / CloudWatch
# ─────────────────────────────────────────────────────────────────────────────

FAILURE_SCENARIOS = [
    {
        "failure_id":   "INC-001",
        "pipeline":     "transactions_daily_load",
        "error_type":   "null_primary_key",
        "error_message": "IntegrityError: null value in column 'transaction_id' violates not-null constraint",
        "rows_affected": 12,
        "dataset":       "transactions_raw.csv",
        "timestamp":     "2026-06-02T02:17:43",
    },
    {
        "failure_id":   "INC-002",
        "pipeline":     "transactions_daily_load",
        "error_type":   "schema_drift",
        "error_message": "ColumnNotFoundError: column 'upi_ref_id' not found in target table",
        "rows_affected": 500,
        "dataset":       "transactions_raw.csv",
        "timestamp":     "2026-06-02T03:44:11",
    },
    {
        "failure_id":   "INC-003",
        "pipeline":     "amount_aggregation",
        "error_type":   "type_mismatch",
        "error_message": "DataError: invalid input syntax for type numeric: '' on column 'amount'",
        "rows_affected": 7,
        "dataset":       "transactions_raw.csv",
        "timestamp":     "2026-06-02T04:02:58",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: DETECT — Check pipeline output for failure signals
# ─────────────────────────────────────────────────────────────────────────────

def detect_failures(scenarios: list) -> list:
    """
    In production: poll CloudWatch logs, Airflow task status, or Snowflake query history.
    Here: return the simulated scenarios directly.
    """
    print(f"  Scanning pipeline logs... {len(scenarios)} active failures detected")
    return scenarios

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: DIAGNOSE — LLM classifies root cause + recommends fix
# ─────────────────────────────────────────────────────────────────────────────

def diagnose_failure(failure: dict) -> dict:
    prompt = f"""You are a data reliability engineer at Sigma DataTech.
A pipeline has failed. Diagnose the root cause and recommend a fix.

Failure details:
{json.dumps(failure, indent=2)}

Respond in JSON only:
{{
  "root_cause_category": "one of: null_data / schema_drift / type_error / timeout / permission / unknown",
  "root_cause_summary": "one sentence",
  "fix_action": "one of: drop_bad_rows / fill_nulls_with_default / add_missing_column / cast_column_type / escalate_to_human",
  "fix_safe_to_automate": true or false,
  "fix_instructions": "specific steps or null if escalate",
  "estimated_data_loss_pct": 0-100
}}"""

    response = call_bedrock(prompt, max_tokens=500)
    try:
        start = response.index("{")
        end   = response.rindex("}") + 1
        return json.loads(response[start:end])
    except Exception:
        return {
            "root_cause_category": "unknown",
            "root_cause_summary":  "Could not parse LLM diagnosis",
            "fix_action":          "escalate_to_human",
            "fix_safe_to_automate": False,
            "fix_instructions":    None,
            "estimated_data_loss_pct": 0,
        }

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: FIX — Apply automated remediation
# ─────────────────────────────────────────────────────────────────────────────

def apply_fix(failure: dict, diagnosis: dict) -> dict:
    """
    Apply automated fix based on diagnosis.

    TODO (STRETCH): Implement the 'cast_column_type' fix action.
    Hint: load the CSV, use pd.to_numeric(df[col], errors='coerce'),
    save the fixed CSV, return {"status": "fixed", "rows_fixed": N}
    """
    action = diagnosis.get("fix_action", "escalate_to_human")
    file_path = os.path.join(DATA_DIR, failure.get("dataset", ""))

    if action == "drop_bad_rows":
        # Drop rows where the problematic column is null/empty
        try:
            df = pd.read_csv(file_path)
            error_col = "transaction_id"  # from the error message context
            before = len(df)
            df = df[df[error_col].notna() & (df[error_col].astype(str).str.strip() != "")]
            after = len(df)
            fixed_path = os.path.join(OUTPUT_DIR, f"fixed_{failure['dataset']}")
            df.to_csv(fixed_path, index=False)
            return {"status": "fixed", "action": action,
                    "rows_dropped": before - after, "output_file": fixed_path}
        except Exception as e:
            return {"status": "fix_failed", "error": str(e)}

    elif action == "fill_nulls_with_default":
        try:
            df = pd.read_csv(file_path)
            numeric_cols = df.select_dtypes(include="number").columns
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            fixed_path = os.path.join(OUTPUT_DIR, f"fixed_{failure['dataset']}")
            df.to_csv(fixed_path, index=False)
            return {"status": "fixed", "action": action,
                    "columns_fixed": list(numeric_cols), "output_file": fixed_path}
        except Exception as e:
            return {"status": "fix_failed", "error": str(e)}

    elif action == "cast_column_type":
        # TODO: Students implement this
        # Hint: The error says '' (empty string) in amount column
        # Fix: cast to numeric, coerce errors to NaN, then fill NaN with 0 or median
        return {"status": "not_implemented",
                "action": action,
                "message": "TODO: Implement cast_column_type fix (see docstring above)"}

    elif action == "escalate_to_human":
        return {"status": "escalated",
                "action": action,
                "message": "Failure requires human review — automated fix not safe"}

    else:
        return {"status": "unknown_action", "action": action}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: RE-RUN — Validate the fix worked
# ─────────────────────────────────────────────────────────────────────────────

def validate_fix(fix_result: dict, failure: dict) -> dict:
    """
    In production: re-run the actual pipeline and check exit code.
    Here: simple file-based validation.
    """
    if fix_result.get("status") == "fixed":
        output_file = fix_result.get("output_file", "")
        if output_file and os.path.exists(output_file):
            df = pd.read_csv(output_file)
            return {"validation": "passed", "clean_rows": len(df),
                    "message": f"Fixed file has {len(df)} clean rows"}
        return {"validation": "failed", "message": "Fixed file not found"}
    return {"validation": "skipped", "message": f"Status: {fix_result.get('status')}"}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: ALERT — Generate incident report
# ─────────────────────────────────────────────────────────────────────────────

def generate_incident_report(failure, diagnosis, fix_result, validation, attempt) -> dict:
    return {
        "incident_id":    failure["failure_id"],
        "timestamp":      datetime.now().isoformat(),
        "pipeline":       failure["pipeline"],
        "original_error": failure["error_message"],
        "heal_attempt":   attempt,
        "diagnosis":      diagnosis,
        "fix_applied":    fix_result,
        "validation":     validation,
        "outcome":        validation.get("validation", "unknown"),
        "alert_required": validation.get("validation") != "passed",
    }

# ─────────────────────────────────────────────────────────────────────────────
# MAIN LOOP: DETECT → DIAGNOSE → FIX → RE-RUN → ALERT
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("SELF-HEAL AGENT — STARTING LOOP")
print("="*60)

print("\nSTEP 1: DETECT")
active_failures = detect_failures(FAILURE_SCENARIOS)

all_incidents = []

for failure in active_failures:
    print(f"\n{'─'*50}")
    print(f"Processing: {failure['failure_id']} — {failure['error_type']}")
    print(f"{'─'*50}")

    healed = False
    for attempt in range(1, MAX_HEAL_ATTEMPTS + 1):
        print(f"\n  Attempt {attempt}/{MAX_HEAL_ATTEMPTS}")

        print("  STEP 2: DIAGNOSE...")
        diagnosis = diagnose_failure(failure)
        print(f"  Root cause: {diagnosis.get('root_cause_category')} — {diagnosis.get('root_cause_summary')}")
        print(f"  Fix action: {diagnosis.get('fix_action')} (safe: {diagnosis.get('fix_safe_to_automate')})")

        if not diagnosis.get("fix_safe_to_automate"):
            print("  → Escalating to human (fix not safe to automate)")
            fix_result  = {"status": "escalated", "action": "escalate_to_human"}
            validation  = {"validation": "skipped", "message": "Human review required"}
            all_incidents.append(generate_incident_report(
                failure, diagnosis, fix_result, validation, attempt))
            break

        print("  STEP 3: FIX...")
        fix_result = apply_fix(failure, diagnosis)
        print(f"  Fix result: {fix_result.get('status')}")

        print("  STEP 4: VALIDATE...")
        validation = validate_fix(fix_result, failure)
        print(f"  Validation: {validation.get('validation')}")

        all_incidents.append(generate_incident_report(
            failure, diagnosis, fix_result, validation, attempt))

        if validation.get("validation") == "passed":
            healed = True
            print(f"  ✓ HEALED after {attempt} attempt(s)")
            break

        if attempt < MAX_HEAL_ATTEMPTS:
            print(f"  Retrying in 1s...")
            time.sleep(1)

    if not healed:
        print(f"  ✗ Could not auto-heal {failure['failure_id']} — escalating")

# Save incident report
report_path = os.path.join(OUTPUT_DIR, "self_heal_incident_report.json")
with open(report_path, "w") as f:
    json.dump({
        "agent": "SelfHealAgent",
        "run_timestamp": datetime.now().isoformat(),
        "total_incidents": len(FAILURE_SCENARIOS),
        "healed": sum(1 for inc in all_incidents if inc["outcome"] == "passed"),
        "escalated": sum(1 for inc in all_incidents if inc["outcome"] == "skipped"),
        "incidents": all_incidents,
    }, f, indent=2)

# ─────────────────────────────────────────────────────────────────────────────
# JUDGMENT QUESTION
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("JUDGMENT QUESTION")
print("="*60)
print("""
  The self-heal agent is set to MAX_HEAL_ATTEMPTS = 3.
  On the 3rd attempt it "fixes" a null-key issue by dropping 15% of rows.
  The pipeline turns green. No alert is fired (outcome = "passed").

  Is this a success? What is the hidden danger?
  What single change would you make to the agent's alerting logic?
""")
judgment = input("  Your answer (1-2 sentences): ").strip() or "NOT ANSWERED"

with open(report_path) as f: data = json.load(f)
data["student_judgment"] = judgment
with open(report_path, "w") as f: json.dump(data, f, indent=2)

# ── Final summary ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("LAB 4 COMPLETE — SELF-HEAL AGENT")
print("="*60)
healed_count = sum(1 for inc in all_incidents if inc["outcome"] == "passed")
print(f"""
  Incidents processed : {len(FAILURE_SCENARIOS)}
  Auto-healed         : {healed_count}
  Escalated to human  : {len(FAILURE_SCENARIOS) - healed_count}

  STRETCH GOAL REMINDER:
    The 'cast_column_type' fix action has a TODO.
    Implement it in apply_fix() — see the hint in the docstring.
    Test it against INC-003 (type_mismatch failure).

  Output: self_heal_incident_report.json
""")
