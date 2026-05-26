"""
SQL Review Agent (Batch Mode) — Day 6, STRETCH GOAL
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
STRETCH GOAL — FOR FAST FINISHERS

This goes beyond running code. You need to THINK.

YOUR TASKS:
  1. Run the agent on queries/ folder (easy — just one command)
  2. Read batch_report.json — understand what bugs AI found
  3. NOW THE REAL WORK: Write your OWN broken SQL query
     - Create: queries/my_query.sql
     - It MUST have at least 2 INTENTIONAL bugs from different categories:
       * Correctness (wrong logic, missing filter, bad join)
       * Performance (correlated subquery, implicit join, no LIMIT)
       * Security (exposes PII like email, no WHERE on sensitive table)
       * Readability (no aliases, cryptic names, no comments)
     - The bugs should be SUBTLE — not obvious syntax errors
  4. Re-run the agent → verify it catches YOUR bugs
  5. If AI misses a bug: WHY? Is the REVIEW_SYSTEM_PROMPT weak somewhere?

SUCCESS CRITERIA:
  - batch_report.json includes your my_query.sql
  - AI found at least 1 issue in your custom query
  - You can explain what bugs you planted and whether AI caught them

═══════════════════════════════════════════════════════════════

WHY THIS MATTERS:
  - Writing broken code ON PURPOSE teaches you what "broken" looks like
  - Testing if AI catches it = understanding AI's blind spots
  - This is exactly what security teams do: write attack queries, test defences

WHERE THIS FITS:
  Day 8: CI/CD runs this on every PR
  Day 10: LangGraph agent calls this as a TOOL autonomously

HOW TO RUN:
  python stretch_goal_sql_review.py queries/
"""

import sys
import os
import glob
import json
from datetime import datetime
import importlib
_mod = importlib.import_module("1_sql_review")
review_sql = _mod.review_sql


def review_file(filepath: str) -> dict:
    """Review a single .sql file and save individual report."""
    with open(filepath, "r") as f:
        sql = f.read()

    print(f"\nReviewing: {filepath}")
    result = review_sql(sql)

    report = {
        "file": filepath,
        "reviewed_at": datetime.now().isoformat(),
        "issues_found": len(result.get("issues", [])),
        "review": result,
    }

    # Save individual report
    report_name = os.path.splitext(os.path.basename(filepath))[0] + "_review.json"
    with open(report_name, "w") as f:
        json.dump(report, f, indent=2)

    # Print 1-line summary
    issues = result.get("issues", [])
    severity_counts = {}
    for issue in issues:
        sev = issue.get("severity", "Unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    severity_str = ", ".join(f"{v} {k}" for k, v in severity_counts.items())
    print(f"  [{len(issues)} issues: {severity_str}] {os.path.basename(filepath)}")

    return report


def review_directory(dirpath: str) -> dict:
    """Review all .sql files in a directory."""
    sql_files = glob.glob(os.path.join(dirpath, "*.sql"))

    if not sql_files:
        print(f"No .sql files found in {dirpath}")
        return {}

    print(f"\nFound {len(sql_files)} SQL files in {dirpath}")
    print("=" * 60)

    all_reports = []
    for filepath in sorted(sql_files):
        report = review_file(filepath)
        all_reports.append(report)

    # Batch summary
    total_issues = sum(r["issues_found"] for r in all_reports)
    batch_report = {
        "directory": dirpath,
        "reviewed_at": datetime.now().isoformat(),
        "files_reviewed": len(all_reports),
        "total_issues": total_issues,
        "files": all_reports,
    }

    with open("batch_report.json", "w") as f:
        json.dump(batch_report, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"BATCH REVIEW COMPLETE")
    print(f"Files reviewed: {len(all_reports)}")
    print(f"Total issues: {total_issues}")
    print(f"Report saved: batch_report.json")
    print(f"{'=' * 60}")

    # Check if student's custom query is included
    custom_files = [f for f in sql_files if "my_query" in f.lower()]
    if custom_files:
        print(f"\n  YOUR CUSTOM QUERY FOUND: {custom_files[0]}")
        custom_report = next((r for r in all_reports if "my_query" in r["file"].lower()), None)
        if custom_report and custom_report["issues_found"] > 0:
            print(f"  AI found {custom_report['issues_found']} issues in your query. Nice work!")
        elif custom_report:
            print(f"  AI found 0 issues. Your bugs are too subtle or the prompt needs improvement.")
    else:
        print(f"\n  NEXT STEP: Create queries/my_query.sql with 2+ intentional bugs, then re-run!")

    return batch_report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("=" * 60)
        print("STRETCH GOAL: SQL Review Agent")
        print("=" * 60)
        print("")
        print("STEP 1: Run the agent on existing queries")
        print("  python stretch_goal_sql_review.py queries/")
        print("")
        print("STEP 2: Read batch_report.json — what bugs did AI find?")
        print("")
        print("STEP 3: Create queries/my_query.sql")
        print("  - Write a SQL query with 2+ INTENTIONAL subtle bugs")
        print("  - Use different categories (correctness + performance, etc.)")
        print("")
        print("STEP 4: Re-run and verify AI catches your bugs")
        print("  python stretch_goal_sql_review.py queries/")
        print("")
        sys.exit(0)

    target = sys.argv[1]

    if os.path.isdir(target):
        review_directory(target)
    elif os.path.isfile(target) and target.endswith(".sql"):
        review_file(target)
    else:
        print(f"Error: '{target}' is not a .sql file or directory")
        sys.exit(1)
