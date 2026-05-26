"""
Code Review Agent — Day 7, Module 5
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
MISSION:
  Your pipeline_brain/generated_pipeline.py was written by AI in 60 seconds.
  Would you merge it to main without reading it?

  This module does what a senior DE does before every merge:
  applies a structured checklist, finds issues, documents them.

  Sigma DataTech lost $47K from a query that "looked fine".
  The rule: AI generates. Humans review. Always.

MANUAL FIRST (do this BEFORE running the script):
  Open pipeline_brain/generated_pipeline.py in a text editor.
  Spend 5 minutes reading it. Write down:
    1. One thing that looks wrong or risky
    2. One thing you would change before putting this in production
  THEN run this script and see how many issues it finds.

WHERE THIS FITS:
  Today: you review AI-generated pipeline code manually + with AI
  Day 8: GitHub Actions runs this review automatically on every PR
  Day 10: An autonomous agent runs this before deciding to deploy

HOW TO RUN:
  python 5_code_review.py
═══════════════════════════════════════════════════════════════
"""

import boto3
import json
import os
from datetime import datetime, timezone

# ── CONFIGURATION ──────────────────────────────────────────────────────────
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
MODEL_ID = "amazon.nova-pro-v1:0"    # Nova Pro for structural reasoning
OUTPUT_DIR = "pipeline_brain"

PIPELINE_FILE = os.path.join(OUTPUT_DIR, "generated_pipeline.py")
REVIEW_OUTPUT = os.path.join(OUTPUT_DIR, "code_review.json")

# ── SYSTEM PROMPT ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a senior Data Engineer at a fintech company conducting a code review.
You are systematic, precise, and focused on production correctness.
You return structured JSON only — no explanations outside the JSON, no markdown fences."""

# ── REVIEW PROMPT ──────────────────────────────────────────────────────────
REVIEW_PROMPT = """You are a senior Data Engineer reviewing AI-generated PySpark pipeline code before production merge.

Review this code against exactly these 12 checkpoints. For each, return: status (PASS/FAIL/WARN), finding (what you found), fix (what to change).

CHECKPOINTS:
1. IDEMPOTENCY: Does every write operation use overwrite mode or delete-partition-first? (FAIL if append mode found)
2. ERROR_HANDLING: Is there try/except around each pipeline stage? (FAIL if bare code with no exception handling)
3. PARTITION_PRUNING: Are read operations filtered by date/partition column? (WARN if full table scans present)
4. ROW_COUNT_LOGGING: Is row count logged after each transformation stage? (WARN if no logging)
5. BUSINESS_RULES: Is revenue calculated as SUM(amount) WHERE status='COMPLETED' only? (FAIL if all statuses included)
6. NULL_HANDLING: Are NULL checks present on primary key and critical columns? (WARN if missing)
7. BROADCAST_HINT: Is broadcast() used on the merchant dimension join (small table)? (WARN if missing)
8. HARDCODED_PATHS: Are file paths hardcoded as strings instead of parameters? (FAIL if hardcoded)
9. SCHEMA_VALIDATION: Is there any check that expected columns exist before transforming? (WARN if missing)
10. DEDUPLICATION: Is there explicit dedup logic on transaction_id? (FAIL if missing for Silver layer)
11. METADATA_OUTPUT: Does the pipeline write a run summary JSON at the end? (WARN if missing)
12. IMPORTS: Are all imports present and specific (not import *)? (FAIL if wildcard imports found)

Return ONLY this JSON structure, no markdown:
{
  "checkpoints": [
    {"id": 1, "name": "IDEMPOTENCY", "status": "PASS|FAIL|WARN", "finding": "...", "fix": "..."},
    {"id": 2, "name": "ERROR_HANDLING", "status": "PASS|FAIL|WARN", "finding": "...", "fix": "..."},
    {"id": 3, "name": "PARTITION_PRUNING", "status": "PASS|FAIL|WARN", "finding": "...", "fix": "..."},
    {"id": 4, "name": "ROW_COUNT_LOGGING", "status": "PASS|FAIL|WARN", "finding": "...", "fix": "..."},
    {"id": 5, "name": "BUSINESS_RULES", "status": "PASS|FAIL|WARN", "finding": "...", "fix": "..."},
    {"id": 6, "name": "NULL_HANDLING", "status": "PASS|FAIL|WARN", "finding": "...", "fix": "..."},
    {"id": 7, "name": "BROADCAST_HINT", "status": "PASS|FAIL|WARN", "finding": "...", "fix": "..."},
    {"id": 8, "name": "HARDCODED_PATHS", "status": "PASS|FAIL|WARN", "finding": "...", "fix": "..."},
    {"id": 9, "name": "SCHEMA_VALIDATION", "status": "PASS|FAIL|WARN", "finding": "...", "fix": "..."},
    {"id": 10, "name": "DEDUPLICATION", "status": "PASS|FAIL|WARN", "finding": "...", "fix": "..."},
    {"id": 11, "name": "METADATA_OUTPUT", "status": "PASS|FAIL|WARN", "finding": "...", "fix": "..."},
    {"id": 12, "name": "IMPORTS", "status": "PASS|FAIL|WARN", "finding": "...", "fix": "..."}
  ],
  "summary": {
    "pass_count": 0,
    "fail_count": 0,
    "warn_count": 0,
    "merge_recommendation": "APPROVE|REJECT|APPROVE_WITH_CHANGES",
    "top_3_fixes": ["fix1", "fix2", "fix3"]
  }
}"""


def run_code_review(pipeline_code: str) -> dict:
    """Send pipeline code to Nova Pro for structured 12-point review."""
    user_prompt = f"{REVIEW_PROMPT}\n\nCODE TO REVIEW:\n{pipeline_code}"

    print(f"\n[Bedrock] Sending {len(pipeline_code):,} chars of pipeline code to {MODEL_ID}...")
    print(f"[Bedrock] Running 12-point engineering checklist...")

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"maxTokens": 3000, "temperature": 0.2},
    )

    raw_text = response["output"]["message"]["content"][0]["text"]
    usage = response["usage"]
    print(f"[Bedrock] Review complete. Tokens: {usage['inputTokens']} in / {usage['outputTokens']} out")

    # Strip markdown fences if AI added them despite instructions
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:])
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]

    return json.loads(cleaned)


def print_results(review: dict) -> None:
    """Print review results in a readable table format."""
    checkpoints = review.get("checkpoints", [])
    summary = review.get("summary", {})

    status_icons = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]"}
    status_colors = {
        "PASS": "\033[92m",
        "FAIL": "\033[91m",
        "WARN": "\033[93m",
    }
    RESET = "\033[0m"

    print(f"\n{'=' * 65}")
    print("  CHECKPOINT RESULTS:")
    print("=" * 65)

    for cp in checkpoints:
        status = cp.get("status", "WARN")
        icon = status_icons.get(status, "[WARN]")
        color = status_colors.get(status, "")
        name = cp.get("name", "").ljust(22)
        finding = cp.get("finding", "")
        cp_id = str(cp.get("id", "?")).rjust(2)
        print(f"  {color}{icon}{RESET} {cp_id}. {name} — {finding}")

    print(f"\n{'=' * 65}")
    rec = summary.get("merge_recommendation", "UNKNOWN")
    rec_color = "\033[92m" if rec == "APPROVE" else ("\033[91m" if rec == "REJECT" else "\033[93m")
    print(f"  MERGE RECOMMENDATION: {rec_color}{rec}{RESET}")
    print(f"  PASS: {summary.get('pass_count', 0)}  |  FAIL: {summary.get('fail_count', 0)}  |  WARN: {summary.get('warn_count', 0)}")

    top3 = summary.get("top_3_fixes", [])
    if top3:
        print(f"\n  TOP 3 FIXES REQUIRED:")
        for i, fix in enumerate(top3, 1):
            print(f"    {i}. {fix}")

    print(f"\n{'=' * 65}")
    print("  STUDENT TASK:")
    print("=" * 65)
    print("  Open pipeline_brain/generated_pipeline.py")
    print("  Fix at least 2 of the FAIL items above")
    print("  Save your fixed version as pipeline_brain/fixed_pipeline.py")
    print("  Document what you changed in pipeline_brain/my_review_notes.txt")


def main():
    # ── PRE-RUN CHECK ──────────────────────────────────────────
    if not os.path.exists(PIPELINE_FILE):
        print(f"\n[ERROR] {PIPELINE_FILE} not found.")
        print("  Run 1_spec_to_pipeline.py first to generate the pipeline.")
        return

    print("\n" + "=" * 65)
    print("  MANUAL FIRST — Do This Before Running!")
    print("=" * 65)
    print("  Open pipeline_brain/generated_pipeline.py in a text editor.")
    print("  Spend 5 minutes reading it. Write down:")
    print("    1. One thing that looks wrong or risky")
    print("    2. One thing you would change before putting this in production")
    print("  THEN come back and press Enter to run the AI review.")
    print("=" * 65)
    input("  [Press Enter when you have your two findings written down] ")

    print("\n" + "=" * 65)
    print("  MODULE 5: Code Review Agent")
    print("  Sigma Intelligence Platform | Day 7")
    print("=" * 65)

    # ── LOAD PIPELINE CODE ─────────────────────────────────────
    with open(PIPELINE_FILE, "r", encoding="utf-8") as f:
        pipeline_code = f.read()
    print(f"  Reviewing: {PIPELINE_FILE} ({len(pipeline_code):,} bytes)")

    # ── RUN REVIEW ─────────────────────────────────────────────
    review = run_code_review(pipeline_code)

    # ── SAVE RESULTS ───────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    review["reviewed_file"] = PIPELINE_FILE
    review["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    review["model"] = MODEL_ID

    with open(REVIEW_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(review, f, indent=2)

    print(f"\n  Saved: {REVIEW_OUTPUT}")

    # ── PRINT RESULTS ──────────────────────────────────────────
    print_results(review)

    # ── DEBRIEF ────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print("  DEBRIEF — What Just Happened")
    print("=" * 65)
    print()
    print("  WHAT JUST HAPPENED:")
    print("    You applied a 12-point engineering review to AI code in 30 seconds.")
    print("    A senior DE takes 2 hours to do the same review manually.")
    print("    The findings above are a starting point — not a final verdict.")
    print()
    print("  WHAT AI GOT RIGHT:")
    print("    1. Correctly identifies append vs overwrite mode (idempotency check)")
    print("    2. Spots missing NULL checks and hardcoded paths reliably")
    print("    3. Finds wildcard imports and missing deduplication in Silver layer")
    print()
    print("  WHAT AI GETS WRONG (check these manually):")
    print("    1. May report PASS on idempotency even when overwrite still")
    print("       duplicates on re-run (partition boundary not checked)")
    print("    2. Cannot assess whether YOUR business rules are correct —")
    print("       only you know whether revenue should include FAILED transactions")
    print("    3. BROADCAST_HINT check assumes merchant table — your team's")
    print("       pipeline may join different tables; AI doesn't know that")
    print()
    print("  THE RULE TO REMEMBER:")
    print("    AI reviews syntax and patterns.")
    print("    You review business correctness. Both are necessary.")
    print()
    print("  WHERE THIS FITS NEXT:")
    print("    Day 8: this runs in GitHub Actions on every PR.")
    print("    Nobody merges unreviewed code.")
    print(f"{'=' * 65}\n")


if __name__ == "__main__":
    main()
