"""
Day 8 — Sprint 4: CI/CD Pipeline + SLOs + Alert Rules
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
MISSION:
  Code reviewed, documented, tested. Still no CI/CD — any
  developer can push broken code to main. And nobody has defined
  what "the pipeline is healthy" means.

  Sprint 4 fixes both:
    - AI generates a GitHub Actions workflow that runs on every PR
    - AI defines SLOs + alert rules that would page the on-call
      engineer at 3 AM if Sigma DataTech's pipeline breaks

  This is how production DataOps teams guarantee reliability.

MANUAL FIRST (do this BEFORE running the script):
  Think about the Sigma DataTech pipeline you've built.
  Take 2 minutes — write down:
    1. One thing that, if broken, you'd want a 3 AM page for
    2. One metric you'd track as a daily health check
    3. What "data freshness SLO" would you set for a financial
       pipeline? (How many hours before stale data is a problem?)
  Write your answers. Then run the script and compare with AI.

WHERE THIS FITS IN THE PLATFORM:
  Sprint 1 (1_pytest_sprint.py):   Tests for correctness
  Sprint 2 (2_soda_sprint.py):     Data quality checks
  Sprint 3 (3_ci_sprint.py):       GitHub Actions CI/CD scaffold
  Sprint 4 (THIS):                 SLOs + alert rules (what is "healthy"?)
  Sprint 5 (5_observability.py):   Evidently AI observability reports

HOW TO RUN:
  cd repo/day8/lab
  python 4_ci_slo.py

OUTPUT:
  devops_brain/pipeline_ci.yml      <- copy this to .github/workflows/
  devops_brain/slo_definitions.json <- your pipeline's health contract
  devops_brain/alert_rules.json     <- who gets paged and when
  devops_brain/ci_slo_report.json   <- combined run report

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

# ── Configuration ──────────────────────────────────────────────────────────────
MODEL_ID_PRO  = "amazon.nova-pro-v1:0"
MODEL_ID_LITE = "amazon.nova-lite-v1:0"
REGION        = "us-east-1"
LAB_DIR       = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR    = os.path.join(LAB_DIR, "devops_brain")
os.makedirs(OUTPUT_DIR, exist_ok=True)

bedrock = boto3.client("bedrock-runtime", region_name=REGION)


# ── Bedrock helper ─────────────────────────────────────────────────────────────
def call_bedrock(model_id: str, prompt: str, max_tokens: int = 3000) -> tuple[str, dict]:
    """
    Call Bedrock Nova and return (response_text, usage_dict).
    Uses invoke_model — same pattern as earlier sprints so students
    can see both converse() and invoke_model() styles across Day 8.
    """
    response = bedrock.invoke_model(
        modelId=model_id,
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


def strip_fences(text: str) -> str:
    """Remove markdown code fences that AI sometimes adds despite instructions."""
    for lang in ("yaml", "json", ""):
        tag = f"```{lang}"
        if tag in text:
            text = text.split(tag, 1)[1]
            if "```" in text:
                text = text.rsplit("```", 1)[0]
            break
    return text.strip()


# ── Step 1: GitHub Actions workflow YAML ──────────────────────────────────────
def generate_ci_workflow() -> tuple[str, dict]:
    """
    Ask Nova Pro to generate a GitHub Actions workflow.
    Saves to devops_brain/pipeline_ci.yml (not .github/workflows/ —
    students copy it manually, which forces them to read it).
    """
    prompt = """You are a senior DevOps engineer teaching B.Tech freshers how CI/CD works.
Generate a GitHub Actions workflow YAML for the Sigma DataTech data pipeline project.

PROJECT STRUCTURE:
  day8/
    lab/
      sample_data.py           # pipeline functions (transform_bronze_to_silver, etc.)
      0_setup_duckdb.py        # creates sigma_platform.duckdb
      devops_brain/
        test_pipeline.py       # pytest suite (Sprint 1)
        checks/
          pipeline_checks.yml  # Soda data quality checks (Sprint 2)

REQUIREMENTS:
1. Workflow name: "Sigma DataTech Pipeline CI"
2. Triggers: push to main, pull_request to main
3. Runs on: ubuntu-latest, Python 3.10
4. Steps — add a comment above EACH step explaining what it does and why:
   a. Checkout code (actions/checkout@v4)
   b. Set up Python 3.10 (actions/setup-python@v5)
   c. Cache pip dependencies (actions/cache@v4) to speed up subsequent runs
   d. Install dependencies: pip install duckdb pytest pytest-cov ruff pandas
   e. Run ruff linter: ruff check day8/lab/ --output-format=github
   f. Set up local DuckDB: python day8/lab/0_setup_duckdb.py
   g. Run pytest: pytest day8/lab/devops_brain/test_pipeline.py -v --tb=short
   h. Generate coverage report: pytest day8/lab/devops_brain/test_pipeline.py --cov=day8/lab --cov-report=term-missing
5. Use fail-fast: true for the strategy matrix (even though it's a single OS — teach the concept)
6. Add a top-level comment block (5-6 lines) explaining what this workflow does in plain English

OUTPUT: Only the YAML. No markdown fences. No explanation outside the YAML.
Start with: name: Sigma DataTech Pipeline CI"""

    print("\n[Bedrock Nova Pro] Step 1: Generating GitHub Actions workflow YAML...")
    text, usage = call_bedrock(MODEL_ID_PRO, prompt, max_tokens=2500)
    yaml_text = strip_fences(text)

    # Ensure it starts with the workflow name even if AI added preamble
    if "name:" not in yaml_text[:100]:
        for i, line in enumerate(yaml_text.splitlines()):
            if line.strip().startswith("name:"):
                yaml_text = "\n".join(yaml_text.splitlines()[i:])
                break

    out_path = os.path.join(OUTPUT_DIR, "pipeline_ci.yml")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(yaml_text)

    lines = len(yaml_text.splitlines())
    tokens_in  = usage.get("inputTokens", "?")
    tokens_out = usage.get("outputTokens", "?")
    print(f"[OK] Saved: devops_brain/pipeline_ci.yml  ({lines} lines)")
    print(f"     Tokens: {tokens_in} in / {tokens_out} out")
    print()
    print("  NOTE: This file goes in .github/workflows/ in your real repo.")
    print("  It is saved to devops_brain/ here so you read it before copying.")
    print("  Every line matters — GitHub reads this on every push to main.")

    return yaml_text, usage


# ── Step 2: SLO definitions ────────────────────────────────────────────────────
def generate_slo_definitions() -> tuple[dict, dict]:
    """
    Ask Nova Pro to define SLOs for the Sigma DataTech pipeline.
    Returns (slo_dict, usage_dict).
    """
    prompt = """You are a senior Site Reliability Engineer (SRE) at a fintech company.
Define Service Level Objectives (SLOs) for a financial data pipeline that processes
payment transactions (Bronze -> Silver -> Gold medallion architecture).

The pipeline runs daily and feeds a dashboard used by the analytics team at 08:00 IST.
Business impact: stale or incorrect data causes wrong financial reports for merchants.

Generate SLO definitions as a JSON object with EXACTLY these four SLOs:

1. "data_freshness_slo" — max hours since the last successful pipeline run before
   the data is considered stale. Choose a value appropriate for a financial pipeline
   that feeds a morning dashboard. Include:
     "threshold_hours": <integer>,
     "reasoning": "<one sentence explaining why you chose this value>",
     "breach_impact": "<one sentence on business consequence of breach>"

2. "quality_threshold_slo" — minimum percentage of Silver layer records that must
   pass all quality checks (non-null ID, positive amount, valid merchant).
     "threshold_pct": <float, 0-100>,
     "reasoning": "<why this number>",
     "breach_impact": "<business consequence>"

3. "row_count_slo" — expected row count bounds for the Silver layer, based on the
   fact that the pipeline processes ~21 clean transactions per day in this dataset.
     "min_rows": <integer>,
     "max_rows": <integer>,
     "buffer_pct": <float, e.g. 20.0>,
     "reasoning": "<why this range>"

4. "pipeline_runtime_slo" — maximum acceptable end-to-end pipeline runtime in minutes.
     "threshold_minutes": <integer>,
     "reasoning": "<why this number>",
     "breach_impact": "<business consequence>"

Also add a top-level "slo_context" field:
  "purpose": "<one sentence on why SLOs matter>",
  "review_cadence": "<how often SLOs should be revisited>",
  "owner": "DataOps Team"

OUTPUT: Pure JSON only. No markdown fences. No explanation outside the JSON."""

    print("\n[Bedrock Nova Pro] Step 2: Generating SLO definitions...")
    text, usage = call_bedrock(MODEL_ID_PRO, prompt, max_tokens=1500)
    json_text = strip_fences(text)

    try:
        slo_data = json.loads(json_text)
    except json.JSONDecodeError:
        # Attempt to extract JSON block if AI added surrounding text
        start = json_text.find("{")
        end   = json_text.rfind("}") + 1
        slo_data = json.loads(json_text[start:end]) if start != -1 else {"raw_response": json_text}

    out_path = os.path.join(OUTPUT_DIR, "slo_definitions.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(slo_data, f, indent=2)

    tokens_in  = usage.get("inputTokens", "?")
    tokens_out = usage.get("outputTokens", "?")
    print(f"[OK] Saved: devops_brain/slo_definitions.json")
    print(f"     Tokens: {tokens_in} in / {tokens_out} out")

    # Show the freshness SLO so students can engage with the accountability gate
    freshness = slo_data.get("data_freshness_slo", {})
    freshness_hours = freshness.get("threshold_hours", "?")
    freshness_reason = freshness.get("reasoning", "")
    print(f"\n  SLO Summary:")
    print(f"    data_freshness:     {freshness_hours} hours  ({freshness_reason})")
    quality = slo_data.get("quality_threshold_slo", {})
    print(f"    quality_threshold:  {quality.get('threshold_pct', '?')}%")
    row_count = slo_data.get("row_count_slo", {})
    print(f"    row_count bounds:   {row_count.get('min_rows', '?')} – {row_count.get('max_rows', '?')}")
    runtime = slo_data.get("pipeline_runtime_slo", {})
    print(f"    pipeline_runtime:   {runtime.get('threshold_minutes', '?')} minutes max")

    return slo_data, usage


# ── Step 3: Alert rules ────────────────────────────────────────────────────────
def generate_alert_rules(slo_data: dict) -> tuple[dict, dict]:
    """
    Ask Nova Lite to generate alert rules derived from the SLO definitions.
    3 CRITICAL, 3 WARNING, 2 INFO — each with actionable remediation steps.
    """
    # Pass the SLOs as context so alert thresholds are consistent
    slo_summary = json.dumps({
        k: v for k, v in slo_data.items()
        if k != "slo_context"
    }, indent=2)

    prompt = f"""You are a DataOps engineer configuring PagerDuty-style alerts for a financial
data pipeline. The SLOs below define what "healthy" means for this pipeline.

SLO DEFINITIONS:
{slo_summary}

Generate alert rules as a JSON object with EXACTLY three keys: "CRITICAL", "WARNING", "INFO".

"CRITICAL" — array of 3 alerts that trigger an immediate page (wakes someone at 3 AM):
  Conditions: pipeline not run in > freshness SLO hours, quality % < SLO threshold,
              row count outside SLO bounds (use the min/max from slo_definitions)

"WARNING" — array of 3 alerts for next-business-day attention:
  Conditions: pipeline runtime approaching SLO limit, quality slightly below threshold,
              one merchant's failure rate suddenly spikes above 30%

"INFO" — array of 2 alerts that are logged silently (no page, no ticket):
  Conditions: new payment method seen in data, daily row count near (but within) bounds

Each alert object must have:
  "name": "<short_snake_case_name>",
  "condition": "<human-readable condition description>",
  "threshold": "<numeric or string value that triggers the alert>",
  "message": "<the exact message sent to the on-call engineer>",
  "recommended_action": "<one sentence: what to do first when this fires>"

OUTPUT: Pure JSON only. No markdown fences. No explanation outside the JSON."""

    print("\n[Bedrock Nova Lite] Step 3: Generating alert rules...")
    text, usage = call_bedrock(MODEL_ID_LITE, prompt, max_tokens=2000)
    json_text = strip_fences(text)

    try:
        alert_data = json.loads(json_text)
    except json.JSONDecodeError:
        start = json_text.find("{")
        end   = json_text.rfind("}") + 1
        alert_data = json.loads(json_text[start:end]) if start != -1 else {"raw_response": json_text}

    out_path = os.path.join(OUTPUT_DIR, "alert_rules.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(alert_data, f, indent=2)

    tokens_in  = usage.get("inputTokens", "?")
    tokens_out = usage.get("outputTokens", "?")
    print(f"[OK] Saved: devops_brain/alert_rules.json")
    print(f"     Tokens: {tokens_in} in / {tokens_out} out")

    # Print a readable alert summary
    print(f"\n  Alert Rule Summary:")
    for severity in ("CRITICAL", "WARNING", "INFO"):
        rules = alert_data.get(severity, [])
        print(f"    {severity} ({len(rules)} rules):")
        for rule in rules:
            name      = rule.get("name", "unnamed")
            threshold = rule.get("threshold", "?")
            print(f"      - {name}  [threshold: {threshold}]")

    return alert_data, usage


# ── Step 4: Combined CI/SLO report ────────────────────────────────────────────
def save_combined_report(
    yaml_text: str,
    slo_data: dict,
    alert_data: dict,
    ci_usage: dict,
    slo_usage: dict,
    alert_usage: dict,
    student_judgment: str,
) -> str:
    """Assemble and save the combined ci_slo_report.json."""
    report = {
        "sprint":          "ci_slo",
        "generated_at":    datetime.now().isoformat(),
        "models_used": {
            "workflow_generation": MODEL_ID_PRO,
            "slo_generation":      MODEL_ID_PRO,
            "alert_generation":    MODEL_ID_LITE,
        },
        "token_usage": {
            "ci_workflow": {
                "input":  ci_usage.get("inputTokens", 0),
                "output": ci_usage.get("outputTokens", 0),
            },
            "slo_definitions": {
                "input":  slo_usage.get("inputTokens", 0),
                "output": slo_usage.get("outputTokens", 0),
            },
            "alert_rules": {
                "input":  alert_usage.get("inputTokens", 0),
                "output": alert_usage.get("outputTokens", 0),
            },
        },
        "files_generated": [
            "devops_brain/pipeline_ci.yml",
            "devops_brain/slo_definitions.json",
            "devops_brain/alert_rules.json",
            "devops_brain/ci_slo_report.json",
        ],
        "ci_workflow_lines": len(yaml_text.splitlines()),
        "slo_count":         len([k for k in slo_data if k != "slo_context"]),
        "alert_count": {
            "CRITICAL": len(alert_data.get("CRITICAL", [])),
            "WARNING":  len(alert_data.get("WARNING", [])),
            "INFO":     len(alert_data.get("INFO", [])),
        },
        "student_judgment": student_judgment if student_judgment.strip() else "NOT ANSWERED",
    }

    out_path = os.path.join(OUTPUT_DIR, "ci_slo_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return out_path


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    # ── Manual First reminder ─────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  MANUAL FIRST — Do This Before Running!")
    print("=" * 65)
    print("  Think about the Sigma DataTech financial pipeline.")
    print("  Write down (2 minutes — no script yet):")
    print()
    print("    1. One thing that should trigger a 3 AM page")
    print("    2. One daily health metric to track")
    print("    3. Your data freshness SLO in hours — and WHY")
    print()
    print("  Keep your notes. You'll compare them with AI output shortly.")
    print("=" * 65)
    input("  [Press Enter when ready to see what AI generates] ")

    print("\n" + "=" * 65)
    print("  SPRINT 4: CI/CD Pipeline + SLOs + Alert Rules")
    print("  Sigma Intelligence Platform | Day 8")
    print("=" * 65)

    # Step 1: GitHub Actions workflow
    yaml_text, ci_usage = generate_ci_workflow()

    # Step 2: SLO definitions
    slo_data, slo_usage = generate_slo_definitions()

    # ── ACCOUNTABILITY GATE ───────────────────────────────────────────────────
    freshness_slo = slo_data.get("data_freshness_slo", {})
    freshness_hours = freshness_slo.get("threshold_hours", "?")

    print("\n" + "─" * 65)
    print(f"  AI set the data freshness SLO to {freshness_hours} hours.")
    print("  → Do you agree? What would YOU set it to for a financial")
    print("    pipeline and why? (1 sentence): ")
    student_judgment = input("  Your answer: ").strip()
    if not student_judgment:
        student_judgment = "NOT ANSWERED"
    print("─" * 65)

    # Step 3: Alert rules
    alert_data, alert_usage = generate_alert_rules(slo_data)

    # Step 4: Combined report
    report_path = save_combined_report(
        yaml_text, slo_data, alert_data,
        ci_usage, slo_usage, alert_usage,
        student_judgment,
    )

    # ── Debrief ───────────────────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print("  DEBRIEF — What Just Happened")
    print("=" * 65)
    print()
    print("  WHAT JUST HAPPENED:")
    print("  AI generated three production-grade DevOps artefacts in under")
    print("  2 minutes: a CI workflow, SLO contracts, and alert rules.")
    print("  In a real team these would take a sprint of back-and-forth")
    print("  between DevOps, SRE, and the data team to agree on thresholds.")
    print("  AI gave you a starting draft — your domain knowledge refines it.")
    print()
    print("  WHAT AI GOT RIGHT:")
    print("    1. CI workflow structure — checkout, lint, test, coverage in")
    print("       the right order, with pip caching for speed")
    print("    2. SLO framing — threshold + reasoning + breach impact is")
    print("       exactly the 3-field format SRE teams use in runbooks")
    print("    3. Alert severity separation — CRITICAL / WARNING / INFO maps")
    print("       to how PagerDuty and OpsGenie are actually configured")
    print()
    print("  WHAT AI GETS WRONG (always check these):")
    print("    1. Freshness SLO is generic — AI doesn't know YOUR batch window.")
    print("       A pipeline that runs at 02:00 and feeds a 08:00 dashboard")
    print("       has a 6-hour natural slack; AI may set 4 or 24 — wrong both ways.")
    print("    2. Row count bounds use dataset size, not production volume.")
    print("       21 rows is a lab dataset. Production pipelines process millions;")
    print("       the min/max buffer must be recalibrated from actual history.")
    print("    3. Alert messages are generic placeholders — 'pipeline not run'")
    print("       doesn't tell the on-call WHERE to look. Real messages include")
    print("       table name, last run timestamp, and a Grafana dashboard link.")
    print()
    print("  THE RULE TO REMEMBER:")
    print("    SLOs are contracts — AI can draft the template, but only the")
    print("    domain team can fill in the numbers that matter to the business.")
    print()
    print("  WHERE THIS FITS NEXT:")
    print("    Sprint 5 (5_observability.py): Evidently AI generates the actual")
    print("    data quality report that would feed these alert thresholds.")
    print(f"{'=' * 65}\n")

    total_in  = (ci_usage.get("inputTokens", 0)
                 + slo_usage.get("inputTokens", 0)
                 + alert_usage.get("inputTokens", 0))
    total_out = (ci_usage.get("outputTokens", 0)
                 + slo_usage.get("outputTokens", 0)
                 + alert_usage.get("outputTokens", 0))

    print(f"  Files generated:")
    print(f"    devops_brain/pipeline_ci.yml")
    print(f"    devops_brain/slo_definitions.json")
    print(f"    devops_brain/alert_rules.json")
    print(f"    devops_brain/ci_slo_report.json")
    print(f"  Total Bedrock tokens: {total_in:,} in / {total_out:,} out")
    print()
    print(f"  Next: python 5_observability.py")


if __name__ == "__main__":
    main()
