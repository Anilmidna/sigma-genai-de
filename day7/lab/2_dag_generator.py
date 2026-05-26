"""
Airflow DAG Generator — Day 7, Module 2
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
MISSION:
  You have a pipeline (from Module 1). Now Sigma DataTech's
  platform team says: "All batch jobs must run through Airflow.
  No cron. No manual triggers. Every job needs retry logic,
  SLA monitoring, and failure alerts."

  Writing DAGs by hand is mechanical — define tasks, wire
  dependencies, set retries, add callbacks. AI excels here
  because DAG structure is almost formulaic.
  Your job: generate a production Airflow DAG in 60 seconds,
  then review the parts only YOU can validate (SLA values,
  operator choices, retry policies).

MANUAL FIRST (do this BEFORE running the script):
  Draw a box-and-arrow DAG on paper right now:
  - What tasks does this pipeline need?
  - In what order do they run?
  - What happens if task 2 fails — does task 3 still run?
  - What retry policy would you set for a financial pipeline?
  Take 2 minutes. THEN run the script and compare.

WHERE THIS FITS IN THE PLATFORM:
  Day 7 (today): AI generates the DAG scaffold
  Day 8 (tomorrow): CI/CD validates DAG syntax on every push
  Day 11: Governance agent monitors DAG run status and
          quarantines bad data before it reaches Gold

HOW TO RUN:
  cd repo/day7/lab
  python 2_dag_generator.py

OUTPUT:
  pipeline_brain/sigma_dag.py         <- the Airflow DAG file
  pipeline_brain/dag_report.json      <- model metadata + task count

IMPORTANT: SPEND 5 MINUTES READING THIS FILE. YOU HAVE A QUIZ ON IT.
═══════════════════════════════════════════════════════════════
"""

import boto3
import json
import os
import re
from datetime import datetime, timezone
from sample_data import PIPELINE_SPEC, DAG_CONFIG

# ── CONFIGURATION ──────────────────────────────────────────────────────────
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
MODEL_ID = "amazon.nova-lite-v1:0"     # DAG structure is formulaic — Lite handles it well
OUTPUT_DIR = "pipeline_brain"

# ── SYSTEM PROMPT ──────────────────────────────────────────────────────────
# Key design decision: ask for PythonOperator (not BashOperator) because
# we want type safety and proper Python error propagation.
# Ask for explicit dependencies via >> (more readable than set_downstream).
SYSTEM_PROMPT = """You are a senior Data Engineer who writes production Airflow DAGs.
You use Apache Airflow 2.8+ syntax (TaskFlow API optional but prefer classic operators).
Your DAGs are clean, well-commented, and production-ready.

Rules for all DAGs you write:
- Use PythonOperator for all Python tasks
- Define task dependencies with >> operator (not set_downstream)
- Add on_failure_callback to the DAG and to each task
- Add SlaMiss callback to the DAG definition
- Use dag.default_args for retries, retry_delay, email settings
- Add docstrings to the DAG and each task callable
- Use dag_id, schedule, start_date from the provided config

Return ONLY Python code. No markdown fences. No explanations."""


def generate_dag(spec: str, dag_config: dict) -> tuple[str, dict]:
    """
    Call Bedrock to generate an Airflow DAG from spec + config.
    Returns (dag_code, usage_dict).
    """
    config_str = json.dumps(dag_config, indent=2)

    user_prompt = f"""Generate an Airflow DAG for this pipeline.

PIPELINE SPEC:
{spec}

DAG CONFIGURATION (use these exact values):
{config_str}

Requirements:
1. Three tasks in this exact order:
   - extract_bronze: ingest raw CSVs to Bronze Parquet
   - transform_silver: clean, enrich, deduplicate to Silver
   - build_gold: generate the 3 Gold aggregation tables

2. Task dependencies: extract_bronze >> transform_silver >> build_gold

3. on_failure_callback that logs: dag_id, task_id, execution_date, error message

4. SLA miss callback that sends an alert with dag_id and execution_date

5. default_args with: owner='data-engineering', retries={dag_config['retries']},
   retry_delay=timedelta(minutes={dag_config['retry_delay_minutes']}),
   email_on_failure=True

6. Each task callable must:
   - Accept **context as kwargs
   - Log start and end with task_instance info
   - Raise on failure (do not swallow exceptions)

7. Add a comment block at the top explaining what this DAG does and its SLA

Use dag_id='{dag_config['dag_id']}', schedule='{dag_config['schedule']}',
start_date=datetime(2024, 1, 1), catchup={dag_config['catchup']}"""

    print(f"\n[Bedrock] Generating Airflow DAG...")
    print(f"[Bedrock] Model: {MODEL_ID}")
    print(f"[Bedrock] DAG ID: {dag_config['dag_id']} | Schedule: {dag_config['schedule']}")

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"maxTokens": 4000, "temperature": 0.3},
    )

    raw_text = response["output"]["message"]["content"][0]["text"]
    usage = response["usage"]
    print(f"[Bedrock] DAG generated. Tokens: {usage['inputTokens']} in / {usage['outputTokens']} out")

    # Strip markdown fences
    code = raw_text.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:])
        if code.rstrip().endswith("```"):
            code = code.rstrip()[:-3]

    return code, usage


def count_tasks(dag_code: str) -> dict:
    """
    Parse the generated DAG code to count task definitions and dependencies.
    Looks for PythonOperator assignments and >> dependency chains.
    """
    # Count PythonOperator instantiations
    task_patterns = re.findall(r"PythonOperator\s*\(", dag_code)
    task_count = len(task_patterns)

    # Count >> dependency declarations
    dep_patterns = re.findall(r">>", dag_code)
    dep_count = len(dep_patterns)

    # Check for on_failure_callback
    has_failure_callback = "on_failure_callback" in dag_code

    # Check for SLA
    has_sla = "sla" in dag_code.lower() or "SlaMiss" in dag_code or "sla_miss" in dag_code.lower()

    return {
        "tasks_found":         task_count,
        "dependencies_found":  dep_count,
        "has_dependencies":    dep_count > 0,
        "has_failure_callback": has_failure_callback,
        "has_sla":             has_sla,
    }


def main():
    # ── MANUAL FIRST REMINDER ──────────────────────────────────
    print("\n" + "=" * 65)
    print("  MANUAL FIRST — Do This Before Running!")
    print("=" * 65)
    print("  Draw a box-and-arrow DAG on paper right now.")
    print("  What tasks? What order? What retry policy for a")
    print("  financial pipeline where late data = wrong dashboards?")
    print("  Take 2 minutes. Then compare your design to AI's output.")
    print("=" * 65)
    input("  [Press Enter when you're ready to see what AI generates] ")

    print("\n" + "=" * 65)
    print("  MODULE 2: Airflow DAG Generator")
    print("  Sigma Intelligence Platform | Day 7")
    print("=" * 65)
    print(f"  Target DAG: {DAG_CONFIG['dag_id']}")
    print(f"  Schedule:   {DAG_CONFIG['schedule']} (daily at 02:00 UTC)")
    print(f"  Retries:    {DAG_CONFIG['retries']} with {DAG_CONFIG['retry_delay_minutes']}-min delay")

    # Generate the DAG
    dag_code, usage = generate_dag(PIPELINE_SPEC, DAG_CONFIG)

    # Analyse the generated output
    analysis = count_tasks(dag_code)
    print(f"\n[Analysis] Tasks found (PythonOperator): {analysis['tasks_found']}")
    print(f"[Analysis] Dependency arrows (>>): {analysis['dependencies_found']}")
    print(f"[Analysis] Has failure callback: {analysis['has_failure_callback']}")
    print(f"[Analysis] Has SLA definition: {analysis['has_sla']}")

    # Save the DAG file
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    dag_path = os.path.join(OUTPUT_DIR, "sigma_dag.py")
    with open(dag_path, "w", encoding="utf-8") as f:
        f.write(dag_code)
    dag_size = os.path.getsize(dag_path)
    print(f"\n[Output] Saved {dag_path} ({dag_size:,} bytes)")

    # Save report
    report = {
        "model":              MODEL_ID,
        "dag_id":             DAG_CONFIG["dag_id"],
        "schedule":           DAG_CONFIG["schedule"],
        "tasks_found":        analysis["tasks_found"],
        "has_dependencies":   analysis["has_dependencies"],
        "has_failure_callback": analysis["has_failure_callback"],
        "has_sla":            analysis["has_sla"],
        "tokens_in":          usage["inputTokens"],
        "tokens_out":         usage["outputTokens"],
        "output_file":        dag_path,
        "output_bytes":       dag_size,
        "generated_at":       datetime.now(timezone.utc).isoformat(),
    }

    report_path = os.path.join(OUTPUT_DIR, "dag_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[Output] Saved {report_path}")

    # ── DEBRIEF ────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print("  DEBRIEF — What Just Happened")
    print("=" * 65)
    print()
    print("  WHAT AI GOT RIGHT:")
    print("    1. DAG structure is formulaic — AI nails imports, context manager,")
    print("       default_args, and task definitions every time")
    print("    2. Dependency arrows (>>) — AI correctly wires extract->transform->gold")
    print("    3. Boilerplate (retries, retry_delay, start_date) — zero thinking needed")
    print()
    print("  WHAT AI GETS WRONG (always check these):")
    print("    1. SLA values — AI picks a number, but 120 min SLA for a financial")
    print("       pipeline is a BUSINESS DECISION. Does your ops team agree?")
    print("    2. Operator choice — AI defaults to PythonOperator, but for EMR jobs")
    print("       you'd use EmrAddStepsOperator. AI doesn't know your infra.")
    print("    3. Callback logic — AI writes a placeholder. The actual Slack/PagerDuty")
    print("       integration is code only you can write (you know the API keys).")
    print()
    print("  THE RULE TO REMEMBER:")
    print("    DAG structure = AI's job. SLA, operator selection, and alert routing")
    print("    = your job. Know the difference.")
    print()
    print("  WHERE THIS FITS NEXT:")
    print("    Day 8: GitHub Actions will validate this DAG syntax on every push.")
    print("    Day 11: The Governance Agent will monitor this DAG's run status")
    print("    and quarantine data if extract_bronze reports missing source files.")
    print(f"{'=' * 65}")
    print()
    print("  Next: open pipeline_brain/sigma_dag.py")
    print("  Review: does the retry policy match your paper design?")
    print("  Question: what operator would you use for a Spark job on EMR?")
    print()


if __name__ == "__main__":
    main()
