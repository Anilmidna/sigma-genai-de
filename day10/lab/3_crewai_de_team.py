"""
==============================================================================
DAY 10 — LAB 3: CREWAI — ROLE-BASED MULTI-AGENT DATA ENGINEERING TEAM
==============================================================================

MISSION BRIEFING
----------------
Sigma DataTech's Monday morning data quality report takes a senior DE 3 hours.
Pull Silver table stats, identify issues, write fix queries, produce a report.

You are replacing that workflow with a 3-agent CrewAI crew:
  Agent 1 — Data Scout:       Explores the Silver table, finds anomalies
  Agent 2 — SQL Surgeon:      Writes targeted fix queries for each issue
  Agent 3 — Quality Guardian: Validates the fixes before they touch production

CrewAI contrast vs LangGraph:
  LangGraph  → you define nodes, edges, state explicitly (graph-first)
  CrewAI     → you define roles, goals, tasks (people-first)
One is not better — they solve different design problems.

WHAT YOU WILL LEARN
-------------------
- CrewAI Agent: role, goal, backstory — how personality drives LLM behaviour
- CrewAI Task: description, expected output, agent assignment
- Sequential vs hierarchical process — when each makes sense
- LLM tool calling in CrewAI vs raw boto3 in LangGraph
- When to choose CrewAI over LangGraph in a real DE platform

MANUAL FIRST (2 minutes)
-------------------------
You are the Data Scout. Open sigma_platform.duckdb and run ONE query that
would reveal the top data quality issue in the Silver transactions table.
Write down the issue and its SQL. Then watch Agent 1 do the same.

==============================================================================
OUTPUT
------
  agent_outputs/crewai_dq_report.json — structured quality report
  agent_outputs/crewai_fix_queries.sql — SQL fix statements from Agent 2
==============================================================================
"""

import os, sys, json, duckdb
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from crewai import Agent, Task, Crew, Process, LLM
except ImportError:
    print("[ERROR] Run: pip install crewai")
    sys.exit(1)

try:
    import boto3
except ImportError:
    print("[ERROR] Run: pip install boto3")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH    = os.path.join(os.path.dirname(__file__), "sigma_platform.duckdb")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "agent_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# AWS region for LiteLLM → Bedrock (uses boto3 default credential chain)
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

# ── LLM setup (CrewAI → LiteLLM → Bedrock) ───────────────────────────────────
llm_pro  = LLM(model="bedrock/amazon.nova-pro-v1:0",  aws_region_name="us-east-1")
llm_lite = LLM(model="bedrock/amazon.nova-lite-v1:0", aws_region_name="us-east-1")

# ── DuckDB helper (used inside task descriptions as context) ──────────────────
def get_silver_snapshot() -> str:
    """Fetch a data quality snapshot of the Silver table to seed the agents."""
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        silver_tables = [t for t in tables if "silver" in t.lower() or "transaction" in t.lower()]
        if not silver_tables:
            silver_tables = tables[:2]

        snapshots = []
        for t in silver_tables[:2]:
            row_count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            null_counts = conn.execute(f"""
                SELECT column_name, null_frac FROM (
                    UNPIVOT (
                        SELECT
                            COUNT(*) FILTER (WHERE transaction_id IS NULL) * 100.0 / COUNT(*) AS transaction_id,
                            COUNT(*) FILTER (WHERE amount IS NULL) * 100.0 / COUNT(*) AS amount
                        FROM {t}
                    ) ON transaction_id, amount
                    INTO NAME column_name VALUE null_frac
                )
            """).fetchall() if "transaction" in t.lower() else []
            neg_count = conn.execute(f"SELECT COUNT(*) FROM {t} WHERE amount < 0").fetchone()[0] if "amount" in [c[0] for c in conn.execute(f"DESCRIBE {t}").fetchall()] else 0
            dup_count = conn.execute(f"SELECT COUNT(*) - COUNT(DISTINCT transaction_id) FROM {t}").fetchone()[0] if "transaction_id" in [c[0] for c in conn.execute(f"DESCRIBE {t}").fetchall()] else 0
            snapshots.append(
                f"Table: {t} | Rows: {row_count} | Negatives: {neg_count} | Duplicates: {dup_count}"
            )
        conn.close()
        return "\n".join(snapshots)
    except Exception as e:
        return f"Snapshot error: {e} — agents will query directly."

def get_schema_str() -> str:
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        parts = []
        for t in tables:
            cols = conn.execute(f"DESCRIBE {t}").fetchall()
            col_str = ", ".join(f"{c[0]}({c[1]})" for c in cols)
            parts.append(f"{t}: {col_str}")
        conn.close()
        return "\n".join(parts)
    except Exception as e:
        return f"Schema error: {e}"

print("Scanning Silver table for agent context...")
silver_snapshot = get_silver_snapshot()
schema_str = get_schema_str()
print(f"Snapshot ready.\n")

# ── Agent 1: Data Scout ───────────────────────────────────────────────────────
data_scout = Agent(
    role="Senior Data Quality Analyst",
    goal="Find ALL data quality issues in the Sigma DataTech Silver layer — nulls, negatives, duplicates, schema violations, and statistical outliers.",
    backstory="""You are a meticulous data analyst who has worked at Sigma DataTech
for 3 years. You know the Silver layer inside-out. You have caught 3 production
bugs that would have cost the company millions. You are obsessed with completeness
— you never say 'looks fine' without checking. You think in SQL.""",
    llm=llm_pro,
    verbose=True,
    allow_delegation=False,
)

# ── Agent 2: SQL Surgeon ──────────────────────────────────────────────────────
sql_surgeon = Agent(
    role="Principal Data Engineer",
    goal="Write precise, safe, idempotent SQL fix queries for each data quality issue identified by the Data Scout.",
    backstory="""You are a battle-hardened DE who has migrated 50TB of data.
You know that every fix query can make things worse if written carelessly.
You always write UPDATE queries with WHERE clauses, never without. You test
on 10 rows before proposing a full-table fix. You write DuckDB-compatible SQL.""",
    llm=llm_pro,
    verbose=True,
    allow_delegation=False,
)

# ── Agent 3: Quality Guardian ─────────────────────────────────────────────────
quality_guardian = Agent(
    role="Data Governance Lead",
    goal="Review every fix query for safety, correctness, and business impact before it touches production data.",
    backstory="""You are the last line of defence before SQL runs in production.
You have seen 5 incidents caused by well-intentioned fix queries. You check
for: missing WHERE clauses, unintended row deletions, business rule violations,
and downstream impact on Gold layer and reports.""",
    llm=llm_lite,
    verbose=True,
    allow_delegation=False,
)

# ── Tasks ─────────────────────────────────────────────────────────────────────
task_scout = Task(
    description=f"""Investigate the Silver transactions table for data quality issues.

Database schema:
{schema_str}

Initial snapshot (pre-computed):
{silver_snapshot}

Your investigation must cover:
1. NULL analysis — which columns have nulls, what % of rows
2. Negative amount check — how many rows have amount < 0
3. Duplicate detection — are there duplicate transaction_ids
4. Statistical outliers — any amounts 3x above average
5. Date integrity — any future-dated transactions

For each issue found, report:
- Issue name
- Row count affected
- Example values (if applicable)
- Severity: CRITICAL / HIGH / MEDIUM / LOW

Write the DuckDB SQL query you would run for each check.
Format your output as a structured list of issues.""",
    expected_output="A structured list of data quality issues with: issue name, severity, affected row count, and detection SQL for each.",
    agent=data_scout,
)

task_surgeon = Task(
    description=f"""Based on the data quality issues identified by the Data Scout,
write a DuckDB-compatible SQL fix query for each issue.

Database schema:
{schema_str}

Requirements for each fix query:
1. Must be idempotent (safe to run multiple times)
2. Must have a WHERE clause — never do full-table updates
3. Add a comment explaining what it fixes and why
4. If a fix could cause downstream issues, note it explicitly
5. Order fixes from safest to riskiest

Also write a ROLLBACK strategy for the top 2 riskiest fixes.

Format each fix as:
-- FIX: [issue name] | SEVERITY: [level] | RISK: [LOW/MEDIUM/HIGH]
[SQL statement]
-- ROLLBACK: [how to undo this]""",
    expected_output="A complete set of numbered SQL fix statements, ordered by risk, with rollback strategies for high-risk fixes.",
    agent=sql_surgeon,
    context=[task_scout],
)

task_guardian = Task(
    description=f"""Review ALL fix queries from the SQL Surgeon.
For each fix query:
1. Check for missing or overly broad WHERE clauses
2. Verify it does NOT delete rows (use UPDATE or INSERT, not DELETE, unless justified)
3. Assess downstream impact on any Gold layer tables
4. Assign: SAFE TO RUN / REVIEW FURTHER / DO NOT RUN

Produce a final sign-off report:
- Executive summary (2 sentences)
- Per-fix verdict with specific reason
- Overall data health score: X/10
- Recommended run order for the approved fixes
- What to monitor after running the fixes""",
    expected_output="A governance sign-off report with per-fix verdicts, an overall data health score, and a recommended run sequence.",
    agent=quality_guardian,
    context=[task_scout, task_surgeon],
)

# ── Crew ──────────────────────────────────────────────────────────────────────
dq_crew = Crew(
    agents=[data_scout, sql_surgeon, quality_guardian],
    tasks=[task_scout, task_surgeon, task_guardian],
    process=Process.sequential,
    verbose=True,
)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*70)
    print("DAY 10 — LAB 3: CrewAI Data Quality Crew")
    print("Sigma DataTech — Monday Morning DQ Report Automation")
    print("="*70 + "\n")

    result = dq_crew.kickoff()

    # Save structured output
    output = {
        "timestamp": datetime.now().isoformat(),
        "crew_output": str(result),
        "tasks_completed": 3,
        "agents": ["Data Scout", "SQL Surgeon", "Quality Guardian"],
    }

    report_path = os.path.join(OUTPUT_DIR, "crewai_dq_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Extract SQL fixes from the crew output and save separately
    crew_text = str(result)
    fix_lines = [line for line in crew_text.split("\n") if line.strip().upper().startswith(("UPDATE", "INSERT", "DELETE", "-- FIX", "-- ROLLBACK"))]
    sql_path = os.path.join(OUTPUT_DIR, "crewai_fix_queries.sql")
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write(f"-- Sigma DataTech Silver Layer Fix Queries\n")
        f.write(f"-- Generated by CrewAI DQ Crew | {datetime.now().isoformat()}\n\n")
        f.write("\n".join(fix_lines) if fix_lines else "-- See crewai_dq_report.json for full output\n")

    print(f"\n[SAVED] {report_path}")
    print(f"[SAVED] {sql_path}")

    # ── Judgment question ─────────────────────────────────────────────────────
    print("\n" + "─"*60)
    print("JUDGMENT QUESTION:")
    print("─"*60)
    print("You have now built agents with both LangGraph (Lab 2) and CrewAI (Lab 3).")
    answer = input("For a production pipeline that runs nightly — which would you choose and why? (1 sentence): ").strip()
    if not answer:
        answer = "NOT ANSWERED"
    output["student_judgment"] = answer
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\n✅ Lab 3 complete.")
    print("   3 agents. 3 roles. 1 crew. Zero manual effort.")
    print("   Next: stretch goal — add agent memory to the crew.")


# ═════════════════════════════════════════════════════════════════════════════
# STUDENT BUILD TASK — Add a 4th agent to the DQ Crew
# Time: 20–25 minutes  |  Mandatory before the day-end debrief
# ═════════════════════════════════════════════════════════════════════════════
#
# The crew currently ends with the Quality Guardian's sign-off report.
# That report is 500+ words. Nobody reads it on a Monday morning.
#
# YOUR TASK: Add a 4th agent — the Incident Reporter — who distils the full
# Guardian report into a 6-line Slack message a VP can read in 20 seconds.
#
# WHY THIS IS THE RIGHT TASK FOR CREWAI:
#   In LangGraph you would add a new node + edge (structural).
#   In CrewAI you add a new role + task (human-like).
#   The difference in approach is the lesson. Feel it as you build.
#
# SUCCESS CRITERION:
#   agent_outputs/slack_notification.txt must exist.
#   It must contain the header *SIGMA DATATECH DATA QUALITY ALERT*
#   and a severity indicator (CRITICAL / WARNING / OK).
# ─────────────────────────────────────────────────────────────────────────────

def student_build_task():

    print("\n" + "═"*70)
    print("STUDENT BUILD TASK — Add the 4th agent: Incident Reporter")
    print("═"*70)
    print("""
WHAT TO BUILD:
  Agent:  incident_reporter
  Task:   task_reporter  (context=[task_guardian])
  Output: agent_outputs/slack_notification.txt

SLACK MESSAGE FORMAT your agent must produce:
  *SIGMA DATATECH DATA QUALITY ALERT*
  *Date:*    <today's date>
  *Status:*  CRITICAL / WARNING / OK
  *Issues:*  <N total — X critical, Y high>
  *Top fix:* <one sentence — the most urgent action>
  *Next review:* <tomorrow's date>

STEPS:
  Step 1 — Define incident_reporter Agent (see skeleton below)
  Step 2 — Define task_reporter Task with context=[task_guardian]
  Step 3 — Create full_crew with all 4 agents + 4 tasks
  Step 4 — Run full_crew.kickoff() and save the Slack message
  Step 5 — Verify slack_notification.txt looks right

IMPORTANT NOTE ON BACKSTORY:
  In the existing 3 agents, read each backstory carefully.
  The SQL Surgeon's backstory says "never without a WHERE clause."
  That one sentence changes how the LLM generates SQL.
  Write the Incident Reporter's backstory to make it ruthlessly concise —
  an agent that has been told off for writing long reports before.
  You will see the output change based on what you write.
""")

    # ── STEP 1: Define the 4th agent ─────────────────────────────────────────
    # Fill in the ??? fields. Do NOT copy-paste from above — write from scratch.
    # The role, goal, and backstory must be YOUR words, not the trainer's.
    # The backstory in particular should make the agent fear verbosity.

    # incident_reporter = Agent(
    #     role="???",          # e.g. "Data Platform Incident Reporter"
    #     goal="???",          # one sentence: what does success look like for this agent?
    #     backstory="""???""", # 2–3 sentences: who is this person, what scares them,
    #                          # what bad thing happened when they wrote a long report?
    #     llm=llm_lite,        # cheapest model — formatting tasks don't need Nova Pro
    #     verbose=True,
    #     allow_delegation=False,
    # )

    # ── STEP 2: Define the reporting task ─────────────────────────────────────
    # context=[task_guardian] is the wire that connects agents in CrewAI.
    # Without it, incident_reporter has NO access to the DQ findings.
    # With it, CrewAI automatically injects task_guardian's output into this task.

    # task_reporter = Task(
    #     description="""Using the Quality Guardian's sign-off report, produce
    # a Slack notification in EXACTLY this format (6 lines, no more):
    #
    # *SIGMA DATATECH DATA QUALITY ALERT*
    # *Date:*    <today>
    # *Status:*  CRITICAL / WARNING / OK   (pick one based on severity found)
    # *Issues:*  <total count> total — <X> critical, <Y> high
    # *Top fix:* <the single most urgent action, one sentence, < 15 words>
    # *Next review:* <tomorrow's date>
    #
    # Do not add any text outside these 6 lines. No preamble, no explanation.""",
    #     expected_output="A 6-line Slack-formatted DQ notification, nothing else.",
    #     agent=incident_reporter,
    #     context=[task_guardian],
    # )

    # ── STEP 3: Build the 4-agent crew ────────────────────────────────────────
    # You cannot modify dq_crew (it already ran). Create a NEW crew called full_crew.
    # Include ALL 4 agents and ALL 4 tasks in the correct sequential order.

    # full_crew = Crew(
    #     agents=[data_scout, sql_surgeon, quality_guardian, incident_reporter],
    #     tasks=[task_scout, task_surgeon, task_guardian, task_reporter],
    #     process=Process.sequential,
    #     verbose=True,
    # )

    # ── STEP 4: Run the full crew and save the Slack message ──────────────────
    # Uncomment when Steps 1–3 are done:

    # result4 = full_crew.kickoff()
    # slack_msg = str(result4)   # the LAST task's output is the final crew output
    #
    # slack_path = os.path.join(OUTPUT_DIR, "slack_notification.txt")
    # with open(slack_path, "w", encoding="utf-8") as f:
    #     f.write(slack_msg)
    # print(f"\n[SAVED] {slack_path}")
    # print("\n── SLACK MESSAGE ──────────────────────────────────────────────")
    # print(slack_msg[:400])
    # print("───────────────────────────────────────────────────────────────")

    # ── STEP 5: Verify and reflect ────────────────────────────────────────────
    # if os.path.exists(os.path.join(OUTPUT_DIR, "slack_notification.txt")):
    #     print("\n✅ SUCCESS: slack_notification.txt exists.")
    #     print()
    #     print("REFLECTION — answer before the day-end debrief:")
    #     try:
    #         q1 = input("1. You wrote the backstory. How did it change the agent output vs your expectation? ").strip()
    #         q2 = input("2. LangGraph vs CrewAI: which felt more natural for THIS workflow and why? ").strip()
    #     except EOFError:
    #         q1 = q2 = "NOT ANSWERED"
    #     print(f"\n  Logged. Show both answers to the trainer at debrief.")
    # else:
    #     print("\n❌ slack_notification.txt not found.")
    #     print("   Check: is task_reporter's context=[task_guardian] set?")
    #     print("   Without context, the reporter has no DQ data to summarise.")

    print("\nComplete Steps 1–5. Show the trainer your slack_notification.txt.")
    print("The key: context=[task_guardian] is the wire between agents in CrewAI.")
    print("In LangGraph the equivalent is the shared TypedDict state.")
    print("Different syntax, same concept — shared data flow.")


if __name__ == "__main__":
    main()
    student_build_task()
