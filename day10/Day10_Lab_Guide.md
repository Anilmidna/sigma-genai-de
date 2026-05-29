# Day 10 Lab Guide — Agentic AI for Data Engineering
## Sigma DataTech | Build Agents That Think, Fix, and Remember

---

## Setup — Do This First (5 minutes)

```bash
# 1. Go to the lab folder
cd repo/day10

# 2. Run the preflight check — fix any ❌ before starting
python tests/validate_day10.py

# 3. Install dependencies
pip install -r lab/requirements.txt

# 4. Move into the lab directory for all labs
cd lab/
```

All labs use the same database (`sigma_platform.duckdb` — Sigma DataTech Silver layer) and write outputs to `lab/agent_outputs/`.

---

## Lab 1 — Build Your Own ReAct Agent From Scratch

### Mission Brief
Sigma DataTech's fraud team asks: *"Which 3 merchants had the most suspicious transaction patterns last month — high volume AND unusual amounts?"*

A junior DE would write 3 separate SQL queries and paste results into a doc. You are going to build an AI agent that answers multi-step questions autonomously — using nothing but Python and Bedrock. No LangGraph. No LangChain. **You build the loop yourself.**

This is Lab 1 because the pain you feel building it manually is exactly why frameworks like LangGraph exist.

### What You Will Learn
- The ReAct loop: Thought → Action → Observation → Repeat → Final Answer
- Why agents need tools (LLMs cannot query databases directly)
- How to parse structured actions from free-text LLM output
- Why runaway agents need iteration caps and why hallucination is dangerous
- The exact problem LangGraph solves — which you build in Lab 2

### Manual-First Exercise (3 minutes — do this BEFORE running any code)
Close your laptop. On paper, write the steps you would take to answer:
> *"Which 3 merchants had the most suspicious transaction patterns?"*

- How many SQL queries would you write?
- What counts as "suspicious"?
- How do you decide when you have enough information to stop?

Write it down. Then run the lab and compare your reasoning chain to the agent's.

### Pre-requisites
- `python tests/validate_day10.py` shows all ✅
- AWS credentials configured (`~/.aws/credentials` or env vars)
- You are inside `repo/day10/lab/`

### Steps

**Step 1 — Read the file header (2 minutes)**
Open `1_react_agent.py` and read the docstring at the top. Understand the three tools the agent has: `query_db`, `get_schema`, `calculate`.

**Step 2 — Run the agent**
```bash
python 1_react_agent.py
```

**Step 3 — Watch the reasoning loop**
In the terminal you will see each step printed:
```
--- Step 1 ---
Thought: I should first look at the database schema...
Action: get_schema
Obs: TABLE silver_transactions: transaction_id VARCHAR, ...

--- Step 2 ---
Thought: Now I need to find merchants with high volume...
Action: query_db
Input: SELECT merchant_id, COUNT(*) as txn_count ...
Obs:   merchant_id  txn_count
       MER_001      4821
       ...
```

Follow each Thought → Action → Observation cycle. Count how many steps the agent takes.

**Step 4 — Answer the judgment question**
At the end, the agent asks you one question. Answer honestly — your answer is saved to `agent_outputs/react_trace.json`.

### Validation
After running, confirm these files exist:
```bash
ls agent_outputs/
# react_trace.json   — full reasoning trace (every Thought/Action/Observation)
# react_answer.txt   — the agent's final answer
```

Open `react_trace.json`. Verify:
- The `"steps"` count shows how many iterations the agent used
- The `"answer"` field contains specific merchant names with numbers
- The `"trace"` array shows every Thought/Action/Observation in sequence

### Debrief
**What just happened:** You built a complete AI reasoning loop — the agent decided its own next step at every iteration, called real tools, and stopped when it had enough information. No framework managed this for you.

**What the agent got right:** It discovered the schema before writing SQL. It correctly interpreted numeric results and ranked merchants.

**What to watch for:** If the agent generates SQL with a wrong column name, it gets a SQL error back as an Observation and must self-correct. This retry logic is fragile — there's no structured way to ensure it improves. Lab 2 fixes this.

**The rule:** An agent is worth the complexity when the query space is too large or dynamic to hardcode SQL — not for simple 2-query reports.

**Where this fits:** Lab 2 rebuilds this agent properly using LangGraph — with state, memory, structured retry, and conditional routing.

### Bonus Challenge
Modify `1_react_agent.py` to ask a different question:
> *"What was the total transaction value for each payment method category in the last 7 days?"*

Change the `question` variable in `main()` and re-run. Observe how the agent adapts its tool calls without any code change.

---

## Lab 2 — LangGraph SQL Agent with Memory

### Mission Brief
Your Lab 1 agent works — but it has no memory, no structured retry, and no way to prevent bad SQL from reaching the database. Sigma DataTech's production team has rejected it.

You will rebuild the same agent in LangGraph: a directed graph where three specialized agent nodes — Generator, Reviewer, Executor — pass state to each other. If the Reviewer rejects the SQL, the graph routes back to the Generator — up to 3 times — before forcing execution. Every approved query is saved to SQLite so the next run starts with context.

### What You Will Learn
- LangGraph's StateGraph: nodes, edges, and conditional routing
- How a TypedDict state object flows between agent nodes
- How to implement a generate → review → fix loop with a round cap
- SQLite-backed agent memory that persists across runs
- How to swap DuckDB for Snowflake in one line without touching agent logic

### Manual-First Exercise (3 minutes)
You are the SQL Reviewer. Read this query:

```sql
UPDATE silver_transactions
SET amount = ABS(amount)
```

Write down: What is wrong with this query? What would you say to the engineer who wrote it? Then watch what the SQL Reviewer agent says about similar queries.

### Pre-requisites
- Lab 1 complete (agent_outputs/ exists)
- `python tests/validate_day10.py` shows all ✅

### Steps

**Step 1 — Read the agent design**
Open `2_langgraph_sql_agent.py`. Find and read:
- `SQLAgentState` — the TypedDict that all nodes share
- `sql_generator_node`, `sql_reviewer_node`, `sql_executor_node` — three node functions
- `route_after_review()` — the conditional edge that decides: retry or proceed
- `AgentMemory` class — SQLite-backed memory

**Step 2 — Run the agent (first time)**
```bash
python 2_langgraph_sql_agent.py
```

You will see the graph execute in sequence. Watch for the reviewer's feedback appearing in the generator's second attempt.

**Step 3 — Run it again immediately**
```bash
python 2_langgraph_sql_agent.py
```

On the second run, notice: the generator's first Thought now references past approved queries from memory. The agent started smarter — zero code change.

**Step 4 — Inspect the SQLite memory**
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('agent_memory.db')
print('== Approved Queries ==')
for row in conn.execute('SELECT question, sql_query, created_at FROM query_history LIMIT 5').fetchall():
    print(row)
conn.close()
"
```

**Step 5 — Answer the judgment question**
The script asks you one question at the end. Answer it.

### Validation
Confirm these files exist:
```bash
ls agent_outputs/
# langgraph_trace.json   — full graph execution with node inputs/outputs
# approved_queries.json  — only SQL that passed review
```

Open `langgraph_trace.json`. Check:
- `"review_rounds"` shows how many times the reviewer ran
- `"approved": true` in the final state
- `"execution_result"` contains actual data from DuckDB

### Debrief
**What just happened:** The LangGraph StateGraph managed all state transitions for you. The Reviewer's feedback flowed into the Generator's next attempt automatically via shared state.

**What the agent got right:** It rejected SQL missing WHERE clauses. It improved on the second attempt using reviewer feedback. Memory made the second run faster.

**What to watch for:** The reviewer sometimes flags valid SQL as risky (false positives). After 3 rounds it runs anyway — which is intentional but means unsafe SQL can still reach the database if the reviewer is too strict. In production, add a human-approval node for `DELETE` and `UPDATE`.

**The rule:** LangGraph for when you need precise control over retries, routing, and state — not when you just want agents to talk to each other.

**Where this fits:** Lab 3 uses CrewAI for the same data quality problem — role-based instead of graph-based. You will pick which approach fits which scenario.

### Bonus Challenge
Add a fourth node: `sql_optimizer_node`. After SQL is approved, have it rewrite the query for performance (add LIMIT, suggest indexes). Insert it between reviewer and executor in the graph.

```python
# Hint: add to the graph
workflow.add_node("optimize", sql_optimizer_node)
workflow.add_edge("review", "optimize")
workflow.add_edge("optimize", "execute")
```

---

## Lab 3 — CrewAI Data Quality Crew

### Mission Brief
Sigma DataTech's Monday morning data quality report takes a senior DE 3 hours: pull Silver table stats, identify issues, write fix queries, get them reviewed. You will replace that workflow with a 3-agent CrewAI crew where each agent has a defined role, goal, and backstory — and they hand work to each other automatically.

| Agent | Role | Model |
|-------|------|-------|
| Data Scout | Finds all data quality issues | Nova Pro |
| SQL Surgeon | Writes fix queries for each issue | Nova Pro |
| Quality Guardian | Reviews every fix before production | Nova Lite |

### What You Will Learn
- CrewAI Agent: how `role`, `goal`, and `backstory` shape LLM behaviour
- CrewAI Task: how `context=[previous_task]` passes output between agents
- Sequential vs hierarchical process — when each makes sense
- How to assign different models to different agents based on task complexity
- When CrewAI is a better choice than LangGraph

### Manual-First Exercise (2 minutes)
You are the Data Scout. Open a Python terminal and run ONE query against the Silver table that would reveal the most important data quality issue:

```bash
python3 -c "
import duckdb
conn = duckdb.connect('sigma_platform.duckdb', read_only=True)
print(conn.execute('SHOW TABLES').fetchall())
# Write your quality check query here
conn.close()
"
```

Write down: what issue did you find? What SQL would fix it? Then watch Agent 1 do the same.

### Pre-requisites
- Lab 2 complete
- `python tests/validate_day10.py` shows all ✅
- Note: this lab runs 3 agents × multiple Bedrock calls. Expect 3–6 minutes to complete.

### Steps

**Step 1 — Read the three agent definitions**
Open `3_crewai_de_team.py`. Find `data_scout`, `sql_surgeon`, `quality_guardian`. For each, read the `backstory`. Notice how the Quality Guardian's backstory is entirely about past incidents and risk — this shapes every response it generates.

**Step 2 — Run the crew**
```bash
python 3_crewai_de_team.py
```

The terminal will show each agent's verbose output. Let it run to completion — do not interrupt.

**Step 3 — Read the outputs**
```bash
# Full quality report with all three agents' outputs
cat agent_outputs/crewai_dq_report.json

# SQL fix queries extracted from the crew output
cat agent_outputs/crewai_fix_queries.sql
```

**Step 4 — Compare to your manual query**
Go back to what you wrote in the Manual-First exercise. Did the Data Scout find the same issue? Did it find more?

**Step 5 — Answer the judgment question**
The script asks: LangGraph or CrewAI for a nightly production pipeline? Answer with a reason.

### Validation
Confirm these files exist:
```bash
ls agent_outputs/
# crewai_dq_report.json   — full crew output including per-agent results
# crewai_fix_queries.sql  — extracted SQL fix statements
```

Open `crewai_fix_queries.sql`. Check:
- Each fix has a `-- FIX:` comment explaining what it fixes
- Each high-risk fix has a `-- ROLLBACK:` strategy
- No bare UPDATE statements without WHERE clauses

### Debrief
**What just happened:** Three agents with distinct personalities worked sequentially. The Guardian's verdict was shaped entirely by its backstory — "last line of defence, has seen 5 production incidents." Change the backstory and the verdict changes.

**What the agent got right:** The Scout systematically checked nulls, negatives, duplicates, and outliers. The Surgeon wrote idempotent fixes. The Guardian caught missing WHERE clauses.

**What to watch for:** The Surgeon sometimes writes fixes that are syntactically correct but violate business rules (e.g., treating refund transactions — which have negative amounts — as data errors). Always review with domain knowledge.

**The rule:** CrewAI when the workflow maps naturally to human roles and the team structure is stable. LangGraph when you need precise control over retry logic and routing.

**Where this fits:** Tomorrow (Day 11) you will add LLM observability to track how much these Bedrock calls cost per run and set up cost alerts.

### Bonus Challenge
Add a fourth agent: **Report Writer**. Its job is to take the Quality Guardian's verdict and produce a 5-bullet executive summary suitable for the CTO. Add it after the guardian with `context=[task_scout, task_surgeon, task_guardian]`.

---

## Lab 4 ★ — Self-Healing Pipeline Agent (Stretch Goal)

*Only attempt this after completing Labs 1–3.*

### Mission Brief
It is 2 AM. A Sigma DataTech pipeline crashes in production. Instead of paging an on-call DE, your self-healing agent catches the failure, reads the error, asks Bedrock to patch the code, re-runs it, and saves the fix to persistent memory — so the next time the same error occurs, it costs zero Bedrock calls to fix.

This is a production pattern used at Databricks Lakehouse Monitoring, AWS Step Functions, and Astronomer.

### What You Will Learn
- Error fingerprinting: identifying recurring failures by error signature
- Safe code execution: subprocess runner with timeout and crash isolation
- Memory-informed repair: agent consults past fixes before calling LLM
- Cache-driven cost savings: second run with same bug = zero LLM calls
- How to escalate to humans when auto-repair is exhausted

### Manual-First Exercise (3 minutes)
The broken pipeline is printed at the top of `4_stretch_goal_agent_memory.py` in the `BROKEN_PIPELINE` variable. Read it. Find all three bugs. Write them on paper.

Then run the lab and watch whether the agent finds the same bugs — and whether it catches all three.

### Pre-requisites
- Labs 1, 2, and 3 complete
- `python tests/validate_day10.py` shows all ✅

### Steps

**Step 1 — Run the agent (first time)**
```bash
python 4_stretch_goal_agent_memory.py
```

Watch the output:
```
ATTEMPT 1/4 — Running pipeline...
❌ Failed. Error: KeyError: 'amounts'
[AI] No cached fix. Calling Bedrock to diagnose...
[AI] Diagnosis: Column name 'amounts' does not exist; correct name is 'amount'

ATTEMPT 2/4 — Running pipeline...
❌ Failed. Error: OperationalError: ...
[AI] No cached fix. Calling Bedrock to diagnose...

ATTEMPT 3/4 — Running pipeline...
✅ Pipeline succeeded on attempt 3!
```

**Step 2 — Run it again immediately (same broken pipeline)**
```bash
python 4_stretch_goal_agent_memory.py
```

This time watch for:
```
[MEMORY] Known fix found! Applying from memory (no LLM call needed).
ATTEMPT 1/4 — Running pipeline...
✅ Pipeline succeeded on attempt 1!
```

**Zero Bedrock calls on the second run.** The fix was served from SQLite cache.

**Step 3 — Inspect the healing log**
```bash
cat agent_outputs/healing_log.json
```

Check:
- `"total_attempts"` — how many runs it took to fix
- `"healing_log"` array — each attempt with error, diagnosis, and whether it came from memory
- `"final_status": "success"`

**Step 4 — Inspect the patched pipeline**
```bash
cat agent_outputs/patched_pipeline.py
```

Compare it to the `BROKEN_PIPELINE` string in the script. Confirm all three bugs are fixed.

**Step 5 — Check memory database**
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('agent_memory.db')
print('== Healing History ==')
for row in conn.execute('SELECT error_fingerprint, error_message, success FROM healing_history').fetchall():
    print(f'  fp={row[0]}, success={bool(row[2])}, error={row[1][:60]}')
conn.close()
"
```

**Step 6 — Answer the judgment question**
The script asks about the biggest risk of auto-patching code in production. Answer honestly.

### Validation
Confirm these files exist:
```bash
ls agent_outputs/
# healing_log.json     — full repair history with timestamps and attempt count
# patched_pipeline.py  — the fixed code the agent produced
```

Confirm `agent_memory.db` contains entries in the `healing_history` table (Step 5 above).

On the SECOND run, confirm `"from_memory": true` appears in the healing log.

### Debrief
**What just happened:** The agent used an error fingerprint (MD5 of last 3 error lines) to check SQLite before every Bedrock call. On the first run it paid for 2–3 LLM diagnoses. On the second run it paid for zero.

**What the agent got right:** It isolated crashes in a subprocess so the healing agent itself never crashed. It fingerprinted errors to avoid duplicate diagnoses. It escalated cleanly when `MAX_HEAL_ATTEMPTS` was reached.

**What to watch for:** The agent can produce a plausible-looking fix that passes the test pipeline but still has logic errors. Auto-patching production databases without a human review gate is dangerous — always add an approval step for anything that touches financial data.

**The rule:** Self-healing is a cost and reliability win for infrastructure failures (bad connections, transient errors, wrong column names). It is NOT a substitute for proper code review before deployment.

**Where this fits:** Day 11 adds LLM observability — you will track exactly how many Bedrock calls each lab made and what they cost, making the cache savings visible in a dashboard.

### Bonus Challenge
Make the healing agent post to Slack when it escalates (after `MAX_HEAL_ATTEMPTS`). Replace the `print("Escalating")` line with a real HTTP POST to a Slack webhook:

```python
import urllib.request, json
def notify_slack(error: str):
    url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    payload = json.dumps({"text": f":red_circle: Pipeline auto-repair failed.\nError: {error[:200]}"})
    req = urllib.request.Request(url, data=payload.encode(), headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)
```

---

## Quick Reference — All Outputs

| File | Lab | What it contains |
|------|-----|-----------------|
| `agent_outputs/react_trace.json` | 1 | Every Thought/Action/Observation step |
| `agent_outputs/react_answer.txt` | 1 | The agent's final merchant analysis |
| `agent_outputs/langgraph_trace.json` | 2 | Full graph execution with node states |
| `agent_outputs/approved_queries.json` | 2 | SQL that passed reviewer verification |
| `agent_outputs/crewai_dq_report.json` | 3 | Full 3-agent quality report |
| `agent_outputs/crewai_fix_queries.sql` | 3 | Fix SQL with comments and rollback plans |
| `agent_outputs/healing_log.json` | 4 | Repair history — attempts, errors, cache hits |
| `agent_outputs/patched_pipeline.py` | 4 | The agent-fixed pipeline code |
| `agent_memory.db` | 2+4 | Shared SQLite — approved queries + fix cache |

## Common Errors and Fixes

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `ModuleNotFoundError: crewai` | Not installed | `pip install crewai litellm` |
| `ModuleNotFoundError: langgraph` | Not installed | `pip install langgraph langchain-core` |
| `botocore.exceptions.NoCredentialsError` | AWS not configured | Run `aws configure` |
| `AccessDeniedException: bedrock` | Model access not enabled | Check Bedrock console → Model access → Enable Nova Pro |
| `duckdb.CatalogException` | Wrong table name in SQL | Run `get_schema` first, check exact table names |
| Agent loops without answering | MAX_ITER hit before Final Answer | Normal — check react_trace.json for the best-effort answer |
