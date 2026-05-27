"""
==============================================================================
DAY 8 — SPRINT 1: DevOps Brain — AI Code Review + Root Cause Analysis
==============================================================================

MISSION BRIEFING
----------------
Sigma DataTech's Bronze→Silver→Gold pipeline failed in production at 2:47 AM.
The on-call engineer is you. You have the script and a stack trace pulled from
CloudWatch. Nobody knows why it worked fine in the dev run yesterday but blew
up after the second execution in prod.

This script does two things:
  1. Calls AWS Bedrock Nova Pro to review buggy_pipeline.py for security
     vulnerabilities and performance anti-patterns — output is a severity-ranked
     bug list (CRITICAL / HIGH / MEDIUM) with line references and fix recommendations.
  2. Analyses the prod stack trace with Nova Lite to produce a plain-English
     root cause analysis and recommended fix — saved for the incident ticket.

WHERE IT FITS
-------------
Sprint 1 output (code_review_report.json + rca_report.json) feeds directly into:
  - Sprint 2  → 2_doc_generator.py uses the bug list to auto-generate inline docs
  - Sprint 3  → 3_ci_sprint.py wires the review step into a GitHub Actions pipeline
  - Competitive Build → teams race to patch all CRITICAL bugs fastest

OUTPUT FILES
------------
  devops_brain/code_review_report.json   — bug list + your judgment call
  devops_brain/rca_report.json           — stack trace root cause analysis

==============================================================================
"""

import sys
import os
import json
import re
import boto3

# Windows UTF-8 stdout fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# ── Model configuration ──────────────────────────────────────────────────────
MODEL_ID_PRO  = "amazon.nova-pro-v1:0"   # heavier reasoning — code review
MODEL_ID_LITE = "amazon.nova-lite-v1:0"  # faster — stack trace RCA
REGION        = "us-east-1"

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
BUGGY_PIPELINE = os.path.join(SCRIPT_DIR, "buggy_pipeline.py")
OUTPUT_DIR     = os.path.join(SCRIPT_DIR, "devops_brain")

# ── Fake prod stack trace (hardcoded — pulled from CloudWatch) ───────────────
PROD_STACK_TRACE = """\
Traceback (most recent call last):
  File "buggy_pipeline.py", line 134, in load_silver
    con.execute("INSERT INTO silver_transactions VALUES (?, ?, ?, ?, ?)",
                [row["transaction_id"], row["amount"], row["status"], row["merchant_id"]])
duckdb.duckdb.ConstraintException: Constraint Error: Duplicate key "TXN001" violates primary key constraint!
  File "buggy_pipeline.py", line 89, in main
    load_silver(silver_rows)
  File "buggy_pipeline.py", line 156, in run_pipeline
    main()
RuntimeError: Pipeline failed at Silver load stage after processing 14 records\
"""


# ── Bedrock helpers ──────────────────────────────────────────────────────────

def get_bedrock_client():
    return boto3.client("bedrock-runtime", region_name=REGION)


def call_nova(client, model_id, system_prompt, user_message):
    body = {
        "messages": [
            {"role": "user", "content": [{"text": user_message}]}
        ],
        "system": [{"text": system_prompt}],
        "inferenceConfig": {
            "maxTokens": 2048,
            "temperature": 0.2,
        },
    }
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


def strip_markdown_fences(text):
    text = re.sub(r"```(?:json|python|sql|bash|text)?\n?", "", text)
    text = re.sub(r"```", "", text)
    return text.strip()


# ── Sprint 1a: Code Review ───────────────────────────────────────────────────

def run_code_review(client, source_code):
    print("\n[Sprint 1a] Sending buggy_pipeline.py to Nova Pro for security + quality review...")

    system_prompt = (
        "You are a senior data engineering security reviewer. "
        "You review Python pipeline scripts for security vulnerabilities, "
        "data quality anti-patterns, and production-readiness issues. "
        "You are precise, direct, and always cite line numbers."
    )

    user_message = f"""Review the following Python data pipeline script.
Identify ALL bugs, security vulnerabilities, and production anti-patterns.

For each issue:
- Assign severity: CRITICAL, HIGH, or MEDIUM
- Quote the exact line or code snippet
- Explain why it is a problem in one sentence
- Give a specific fix recommendation

Sort your findings from CRITICAL down to MEDIUM. Use this format for each:

[SEVERITY] — Short title
  Line/location: <where in the code>
  Problem: <one sentence>
  Fix: <specific recommendation>

---
SCRIPT TO REVIEW:
---
{source_code}
"""

    raw = call_nova(client, MODEL_ID_PRO, system_prompt, user_message)
    return strip_markdown_fences(raw)


# ── Sprint 1b: Stack Trace RCA ───────────────────────────────────────────────

def run_rca(client, stack_trace):
    print("\n[Sprint 1b] Sending prod stack trace to Nova Lite for root cause analysis...")

    system_prompt = (
        "You are an on-call data engineering SRE. "
        "You analyse Python stack traces from production pipelines and produce "
        "plain-English root cause analyses suitable for incident tickets. "
        "Be concise and actionable — no waffle."
    )

    user_message = f"""Analyse the following production stack trace from Sigma DataTech's pipeline.

Produce:
1. ROOT CAUSE — one paragraph explaining exactly what went wrong and why
2. IMMEDIATE FIX — the specific code change needed to prevent this failure
3. PREVENTION — one sentence on how to catch this class of bug in CI before it reaches prod

---
STACK TRACE:
---
{stack_trace}
"""

    raw = call_nova(client, MODEL_ID_LITE, system_prompt, user_message)
    return strip_markdown_fences(raw)


# ── Accountability Gate ──────────────────────────────────────────────────────

def accountability_gate(review_text):
    print("\n" + "=" * 70)
    print(review_text)
    print("=" * 70)

    bug_count = review_text.upper().count("[CRITICAL]") + \
                review_text.upper().count("[HIGH]") + \
                review_text.upper().count("[MEDIUM]")

    print(f"\nAI found {bug_count} bugs above. Look at the list carefully.")
    answer = input(
        "→ Which ONE would you fix first in a production incident, and why? (1 sentence): "
    ).strip()

    if not answer:
        student_judgment = "NOT ANSWERED"
        print("  (No answer recorded — this will show in check_submissions.py)")
    else:
        student_judgment = answer
        print("  Judgment recorded.")

    return student_judgment


# ── Save outputs ─────────────────────────────────────────────────────────────

def save_outputs(review_text, student_judgment, rca_text):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    review_report = {
        "sprint": "Sprint 1 — Code Review",
        "model": MODEL_ID_PRO,
        "source_file": "buggy_pipeline.py",
        "review": review_text,
        "student_judgment": student_judgment,
    }
    review_path = os.path.join(OUTPUT_DIR, "code_review_report.json")
    with open(review_path, "w", encoding="utf-8") as f:
        json.dump(review_report, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {review_path}")

    rca_report = {
        "sprint": "Sprint 1 — Root Cause Analysis",
        "model": MODEL_ID_LITE,
        "stack_trace": PROD_STACK_TRACE,
        "rca": rca_text,
    }
    rca_path = os.path.join(OUTPUT_DIR, "rca_report.json")
    with open(rca_path, "w", encoding="utf-8") as f:
        json.dump(rca_report, f, indent=2, ensure_ascii=False)
    print(f"Saved: {rca_path}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    # 1. Load source code
    if not os.path.exists(BUGGY_PIPELINE):
        print(f"ERROR: buggy_pipeline.py not found at {BUGGY_PIPELINE}")
        print("Run this script from the day8/lab/ directory and ensure buggy_pipeline.py exists.")
        sys.exit(1)

    with open(BUGGY_PIPELINE, "r", encoding="utf-8") as f:
        source_code = f.read()

    print("=" * 70)
    print("DAY 8 — SPRINT 1: AI Code Review + Root Cause Analysis")
    print("Target: buggy_pipeline.py  |  Models: Nova Pro + Nova Lite")
    print("=" * 70)

    # 2. Connect to Bedrock
    try:
        client = get_bedrock_client()
    except Exception as e:
        print(f"ERROR: Could not create Bedrock client: {e}")
        sys.exit(1)

    # 3. Code review (Nova Pro)
    try:
        review_text = run_code_review(client, source_code)
    except Exception as e:
        print(f"ERROR during code review: {e}")
        sys.exit(1)

    # 4. Accountability gate — student must engage before saving
    student_judgment = accountability_gate(review_text)

    # 5. Stack trace RCA (Nova Lite)
    print("\n[Stack Trace from CloudWatch Logs]")
    print("-" * 50)
    print(PROD_STACK_TRACE)
    print("-" * 50)

    try:
        rca_text = run_rca(client, PROD_STACK_TRACE)
    except Exception as e:
        print(f"ERROR during RCA: {e}")
        sys.exit(1)

    print("\n[Root Cause Analysis]")
    print("-" * 50)
    print(rca_text)
    print("-" * 50)

    # 6. Save both reports
    save_outputs(review_text, student_judgment, rca_text)

    print("\nSprint 1 complete.")
    print("Next: python 2_doc_generator.py")


if __name__ == "__main__":
    main()
