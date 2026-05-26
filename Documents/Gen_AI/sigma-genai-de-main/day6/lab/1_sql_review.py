"""
SQL Review Agent — Day 6, Module 1
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
MISSION:
  The analytics team submitted 3 queries for tomorrow's board deck.
  Last quarter, a "working" query cost Sigma DataTech $47K in wrong
  revenue numbers. Your job: build an AI system that reviews SQL
  like a senior engineer — finds bugs BEFORE they hit production.

WHY THIS MATTERS (vs just pasting SQL into ChatGPT):
  - Structured JSON output -> can plug into CI/CD (Day 8)
  - Schema-grounded -> AI knows YOUR tables, not generic SQL
  - Repeatable -> run on every PR, not one-off manual pastes
  - Auditable -> review_report.json proves what was checked

WHERE THIS FITS IN THE PLATFORM:
  Today: standalone review script
  Day 8: becomes a CI/CD check on every pull request
  Day 10: becomes a TOOL that an autonomous agent can call

IMPORTANT: SPEND 5 MINS TO REVIEW THE CODE. YOU HAVE A QUIZ ON THIS LATER.
═══════════════════════════════════════════════════════════════

HOW TO RUN:
  python 1_sql_review.py
"""

import boto3
import json
from datetime import datetime
from sample_data import SCHEMA_COMPACT, BROKEN_QUERIES

# ── CONFIGURATION ──────────────────────────────────────────
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
MODEL_ID = 'amazon.nova-lite-v1:0'


# ── THE REVIEW PROMPT ──────────────────────────────────────
# Production-grade prompt structure:
#   1. Clear role definition
#   2. Explicit review categories (4)
#   3. Forced JSON output format (so we can parse programmatically)
#   4. "ONLY JSON" instruction (prevents AI adding explanations)

REVIEW_SYSTEM_PROMPT = """You are a senior Data Engineer performing a code review on SQL queries.
You review for exactly 4 categories:
1. CORRECTNESS — logic bugs (wrong results, missing filters, bad joins)
2. PERFORMANCE — anti-patterns (correlated subqueries, missing partition pruning, implicit joins)
3. SECURITY — PII exposure, SQL injection risk, overly broad access
4. READABILITY — naming, formatting, lack of comments on complex logic

For each issue found, return this EXACT JSON structure:
{
  "issues": [
    {
      "severity": "Critical|High|Medium|Low",
      "category": "Correctness|Performance|Security|Readability",
      "title": "short title",
      "line": "approximate line or clause",
      "problem": "1-2 sentence explanation",
      "fix": "corrected SQL snippet"
    }
  ],
  "corrected_sql": "the complete fixed SQL query",
  "summary": "1-2 sentence overall assessment"
}

Return ONLY valid JSON. No markdown fences. No text before or after the JSON."""


def review_sql(sql_query: str) -> dict:
    """
    Send SQL to Bedrock Nova for structured code review.
    Returns parsed JSON report with issues, corrected_sql, summary.
    """
    user_prompt = f"""Review this SQL query against the following schema.

SCHEMA:
{SCHEMA_COMPACT}

SQL TO REVIEW:
{sql_query}

Find ALL bugs across all 4 categories. Be thorough. Return JSON only."""

    print(f"\n[Bedrock] Sending SQL for review ({len(sql_query)} chars)...")

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": REVIEW_SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"maxTokens": 2000, "temperature": 0.2},
    )

    raw_text = response["output"]["message"]["content"][0]["text"]
    tokens_in = response["usage"]["inputTokens"]
    tokens_out = response["usage"]["outputTokens"]
    print(f"[Bedrock] Response received. Tokens: {tokens_in} in / {tokens_out} out")

    # Parse JSON from response (handle cases where AI adds markdown fences)
    clean_text = raw_text.strip()
    if clean_text.startswith("```"):
        clean_text = clean_text.split("\n", 1)[1]
        clean_text = clean_text.rsplit("```", 1)[0]

    try:
        report = json.loads(clean_text)
        print(f"[Parser] Successfully parsed {len(report.get('issues', []))} issues")
        return report
    except json.JSONDecodeError as e:
        print(f"[Parser] JSON parse failed: {e}")
        print(f"[Parser] Raw response:\n{raw_text[:500]}")
        return {"issues": [], "summary": "Parse error — see raw response", "raw": raw_text}


def batch_review():
    """Review all broken queries and save combined report."""
    full_report = {
        "reviewed_at": datetime.now().isoformat(),
        "model": MODEL_ID,
        "queries": {}
    }

    for name, query_data in BROKEN_QUERIES.items():
        print(f"\n{'-' * 60}")
        print(f"Reviewing: {name}")
        print(f"{'-' * 60}")
        result = review_sql(query_data["sql"])
        full_report["queries"][name] = {
            "sql": query_data["sql"],
            "issues_found": len(result.get("issues", [])),
            "review": result,
        }

        # Show what AI found (so students see the value)
        for issue in result.get("issues", []):
            severity = issue.get("severity", "?")
            category = issue.get("category", "?")
            title = issue.get("title", "?")
            problem = issue.get("problem", "")
            print(f"  [{severity}] {category}: {title}")
            print(f"       -> {problem}")

        if result.get("summary"):
            print(f"\n  Summary: {result['summary']}")

    # Save report
    with open("review_report.json", "w") as f:
        json.dump(full_report, f, indent=2)

    total_issues = sum(
        q["issues_found"] for q in full_report["queries"].values()
    )

    print(f"\n{'=' * 60}")
    print(f"BATCH REVIEW COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Queries reviewed: {len(BROKEN_QUERIES)}")
    print(f"  Total issues found: {total_issues}")
    print(f"  Report saved: review_report.json")
    print(f"\n  WHAT JUST HAPPENED:")
    print(f"  -> You fed 3 broken SQL queries to Bedrock Nova")
    print(f"  -> AI reviewed each for: Correctness, Performance, Security, Readability")
    print(f"  -> Got structured JSON back (not free text - parseable by machines)")
    print(f"  -> Saved full report to review_report.json")
    print(f"\n  WHY THIS MATTERS:")
    print(f"  -> This runs in 10 seconds. A human reviewer takes 30 minutes per query.")
    print(f"  -> On Day 8, this becomes a CI/CD check: every PR auto-reviewed before merge.")
    print(f"  -> On Day 10, an autonomous agent calls this without you triggering it.")
    print(f"\n  NEXT: Open review_report.json and read the actual bugs AI found.")
    print(f"        Do you agree with its findings? Any false positives?")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    batch_review()
