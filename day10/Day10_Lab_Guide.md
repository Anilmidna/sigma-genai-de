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
**Total time: ~45 minutes** (Phase A: 15 min + Phase B: 25 min + debrief: 5 min)

### Mission Brief
Sigma DataTech's fraud team asks: *"Which 3 merchants had the most suspicious transaction patterns last month — high volume AND unusual amounts?"*

A junior DE would write 3 separate SQL queries and paste results into a doc. You are going to build an AI agent that answers multi-step questions autonomously — using nothing but Python and Bedrock. No LangGraph. No LangChain. **You build the loop yourself.**

This is Lab 1 because the pain of building it manually is exactly why frameworks like LangGraph exist.

### What You Will Learn
- The ReAct loop: Thought → Action → Observation → Repeat → Final Answer
- Why agents need tools (LLMs cannot query databases directly)
- How to parse structured actions from free-text LLM output
- Why runaway agents need iteration caps
- How to add new tools and why the system prompt matters more than you expect

### Manual-First Exercise (3 minutes — close your laptop)
On paper, write the steps you would take to answer:
> *"Which 3 merchants had the most suspicious transaction patterns?"*

- How many SQL queries would you write?
- What counts as "suspicious"?
- How do you decide when to stop?

Then **predict: how many Thought → Action → Observation cycles** will the agent need?  
Write your number down. The script will ask you for it before running.

### Pre-requisites
- `python tests/validate_day10.py` shows all ✅
- AWS credentials configured
- You are inside `repo/day10/lab/`

---

### Phase A — Run the Agent (15 minutes)

**Step 1** — Open `1_react_agent.py`. Read the 3 tool functions: `tool_query_db`, `tool_get_schema`, `tool_calculate`. Understand what each one does in one sentence each.

**Step 2** — Run the agent:
```bash
python 1_react_agent.py
```
The script will ask for your step-count prediction before the agent runs. Enter it.

**Step 3** — Watch each Thought → Action → Observation cycle print in the terminal. Count as you go.

**Step 4** — When it finishes, check your prediction against the actual step count. If you were off by more than 1, open `react_trace.json` and find the step that surprised you.

**Step 5** — Answer the judgment question the script asks. Your answer is saved.

**Validation:**
```bash
ls agent_outputs/
# react_trace.json   — full reasoning trace
# react_answer.txt   — the agent's final answer
```
Open `react_trace.json`. Confirm `"answer"` contains specific merchant names with numbers.

---

### Phase B — Build Task: Add a 4th Tool (25 minutes, mandatory)

**This is not optional. You do not move to Lab 2 until your `flagged_merchants.json` exists.**

The agent currently has 3 tools: `query_db`, `get_schema`, `calculate`. You will add a 4th: `flag_merchant`.

Open `1_react_agent.py` and scroll to the `student_build_task()` function at the bottom. Follow Steps 1–5 in the comments:

1. **Implement `tool_flag_merchant`** — parse `merchant_id` and `reason` from the input string, append to `agent_outputs/flagged_merchants.json`, return a confirmation string
2. **Register it in `TOOLS`** — one line: `TOOLS["flag_merchant"] = tool_flag_merchant`
3. **Add its description to `TOOL_DESCRIPTIONS`** — this is the most important step. Without it the agent never knows the tool exists
4. **Uncomment the flag_question block** and re-run
5. **Verify** — `flagged_merchants.json` must exist with at least 1 entry. `react_trace.json` must show `Action: flag_merchant` at least once

**Success criterion:** Open `react_trace.json`. Find the `"Thought"` that immediately preceded `Action: flag_merchant`. Read it. That is the agent's reasoning chain for choosing your tool. Answer: does it make sense?

**Show this to the trainer before Lab 2.**

---

### Debrief
**What just happened:** You built the full loop AND extended it. Adding a tool required: write a function + 2 lines of registration. That contract is identical in LangChain, LangGraph, and Bedrock Agents — just with decorators.

**What the agent got right:** Schema discovery before SQL. Numeric ranking. Tool selection based on task context.

**What to watch for:** The agent decided when to call `flag_merchant` based solely on what you wrote in `TOOL_DESCRIPTIONS`. Change that description and the agent's behaviour changes — with no code change. This is prompt engineering at the tool level.

**The rule:** An agent is worth the complexity when the query space is too large or dynamic to hardcode SQL. For a 2-query report, just write the SQL.

**Where this fits:** Lab 2 rebuilds this with LangGraph — adding typed state, structured retry, memory, and Snowflake connectivity.

---

## Lab 2 — LangGraph SQL Agent with Memory
**Total time: ~50 minutes** (Phase A: 20 min + Phase B: 25 min + debrief: 5 min)

### Mission Brief
Your Lab 1 agent works — but it has no memory, no structured retry, and no way to prevent bad SQL from reaching the database. Sigma DataTech's production team has rejected it.

You will run a LangGraph solution — 3 nodes, typed state, conditional routing, SQLite memory — and then **build your own 2-node LangGraph from scratch** to prove you understand the 3 building blocks, not just watched them run.

### What You Will Learn
- LangGraph StateGraph: nodes, edges, conditional routing
- TypedDict state — the only way data moves between nodes
- Conditional edges — routing decisions based on state, not code flow
- SQLite-backed memory that persists across runs
- Snowflake swap pattern — one-line DB switch

### Manual-First Exercise (3 minutes)
You are the SQL Reviewer. Read this query:
```sql
SELECT * FROM silver_transactions
```
Write down 3 specific things wrong with it from a production data engineering perspective. Then watch what the SQL Reviewer agent finds.

### Pre-requisites
- Lab 1 Build Task complete (`flagged_merchants.json` exists)
- `python tests/validate_day10.py` shows all ✅

---

### Phase A — Run the Agent (20 minutes)

**Step 1** — Open `2_langgraph_sql_agent.py`. Read these 4 things:
- `SQLAgentState` TypedDict — every field shared between nodes
- `route_after_review()` function — this is the conditional edge, not a node
- `build_graph()` — note how `add_conditional_edges` differs from `add_edge`
- The Snowflake swap comment in `sql_executor_node` — 4 lines, no agent logic changes

**Step 2** — Run it:
```bash
python 2_langgraph_sql_agent.py
```
Watch for `[Agent 2 — SQL Reviewer] ❌ REJECTED` — if it appears, the generator gets feedback and rewrites the SQL. That retry is the graph routing back automatically.

**Step 3** — Run it a second time immediately:
```bash
python 2_langgraph_sql_agent.py
```
The generator now says "MEMORY — PAST QUERIES: ..." in its prompt. Same agent, smarter start, zero code change.

**Step 4** — Inspect SQLite memory:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('agent_memory.db')
for row in conn.execute('SELECT question, review_rounds, timestamp FROM query_history').fetchall():
    print(row)
conn.close()
"
```

**Validation:**
```bash
ls agent_outputs/
# langgraph_trace.json   — full graph execution
# approved_queries.json  — SQL that passed review
```
Confirm `"approved": true` and `"execution_result"` has data in `langgraph_trace.json`.

---

### Phase B — Build Task: Your Own 2-Node LangGraph (25 minutes, mandatory)

**You do not move to Lab 3 until both test cases pass.**

Open `2_langgraph_sql_agent.py`, scroll to `student_build_task()` at the bottom. Build a 2-node SQL safety graph from scratch.

**What you are building:**
```
NL query → sql_checker_node → (safe?) → safe_executor_node → result
                              (unsafe) → safe_executor_node → "BLOCKED: ..."
```

**Steps in the code:**
1. **Define `CheckerState`** — TypedDict with `sql`, `is_safe`, `check_reason`, `result`
2. **Write `sql_checker_node`** — no LLM needed, just check if `"WHERE"` is in the SQL string
3. **Write `safe_executor_node`** — run via DuckDB if safe, return blocked message if not
4. **Write `route_by_safety`** — returns `"execute"` or `"blocked"` (string, not bool)
5. **Wire the graph** — StateGraph → add_node × 3 → set_entry_point → add_conditional_edges → add_edge × 2 → compile
6. **Uncomment Step 6** — test with a safe SQL and an unsafe SQL

**Success criterion:** Safe SQL returns actual data. Unsafe SQL returns `"BLOCKED: ..."`. Both must work. Show the trainer.

**The 3 concepts you just used:** TypedDict state + node functions + conditional edges. That is all of LangGraph. Everything else is just more of these 3.

---

### Debrief
**What just happened:** You didn't just watch a graph run — you built one. The checker graph is minimal but it is a real LangGraph. Scale it up with Bedrock calls, more nodes, more routing conditions and you have the full Lab 2 agent.

**What the agent got right:** Typed state prevented bugs. Conditional routing made retry logic explicit. Memory made repeated questions cheaper.

**What to watch for:** The reviewer can false-positive on valid SQL (marks it REJECTED when it is fine). After 3 rounds it forces execution anyway — unsafe SQL can still reach the DB. For financial data, add a human-approval node before any UPDATE or DELETE.

**The rule:** LangGraph when you need precise control over state flow and retry. CrewAI (Lab 3) when the workflow maps to human roles and you want less boilerplate.

**Where this fits:** Lab 3 solves the same problem with CrewAI — different mental model, compare both.

---

## Lab 3 — CrewAI Data Quality Crew
**Total time: ~50 minutes** (Phase A: 20 min + Phase B: 25 min + debrief: 5 min)

### Mission Brief
Sigma DataTech's Monday morning data quality report takes a senior DE 3 hours: pull Silver table stats, identify issues, write fix queries, get them reviewed. You will run a 3-agent CrewAI crew that automates this — then **add a 4th agent yourself**.

### What You Will Learn
- CrewAI Agent: how `role`, `goal`, and `backstory` drive LLM behaviour
- CrewAI Task: how `context=[previous_task]` wires agent output to agent input
- Why backstory matters more than you expect — changing 2 sentences changes the output
- Sequential vs hierarchical process — when each applies
- How CrewAI's people-first model differs from LangGraph's graph-first model

### Manual-First Exercise (2 minutes)
You are the Data Scout. Run ONE SQL query that reveals the most important data quality issue in the Silver table:
```bash
python3 -c "
import duckdb
conn = duckdb.connect('sigma_platform.duckdb', read_only=True)
# Write your quality check query here — try: nulls, negatives, duplicates
conn.close()
"
```
Write down: what issue did you find? What severity? Then compare to what Agent 1 reports.

### Pre-requisites
- Lab 2 Build Task complete (both test cases passed)
- `python tests/validate_day10.py` shows all ✅
- This lab makes multiple Bedrock calls — expect 3–6 minutes to complete

---

### Phase A — Run the Crew (20 minutes)

**Step 1** — Open `3_crewai_de_team.py`. For each of the 3 agents, read only the `backstory`. Notice: the SQL Surgeon's backstory says "never without WHERE clauses" — one sentence that changes every query it generates. The Quality Guardian's backstory lists 5 past incidents.

**Step 2** — Run the crew:
```bash
python 3_crewai_de_team.py
```
It will take 3–6 minutes. Watch each agent's output as it completes.

**Step 3** — Compare the Scout's findings to your manual query:
```bash
cat agent_outputs/crewai_dq_report.json
cat agent_outputs/crewai_fix_queries.sql
```
Did the Scout find the same issue you found? Did it find more? Did it miss yours?

**Step 4** — Read `crewai_fix_queries.sql`. Check that every UPDATE has a WHERE clause. If any does not, that is the Surgeon failing its own backstory.

**Step 5** — Answer the judgment question (LangGraph vs CrewAI for a nightly pipeline).

**Validation:**
```bash
ls agent_outputs/
# crewai_dq_report.json   — full 3-agent output
# crewai_fix_queries.sql  — SQL with comments and rollback plans
```

---

### Phase B — Build Task: Add the 4th Agent (25 minutes, mandatory)

**You do not finish Lab 3 until `slack_notification.txt` exists.**

The 3-agent crew ends with a 500-word Guardian report. Nobody reads that on a Monday morning. Add a 4th agent — the Incident Reporter — who distils it into a 6-line Slack message.

Open `3_crewai_de_team.py`, scroll to `student_build_task()`. Follow Steps 1–5:

1. **Define `incident_reporter`** — write the `role`, `goal`, and `backstory` yourself. The backstory should make this agent ruthlessly concise — someone who was reprimanded once for writing a long report. This is not a cosmetic exercise: your backstory will change the output.
2. **Define `task_reporter`** — description specifies the 6-line Slack format exactly. `context=[task_guardian]` is the one line that connects this agent to the crew's findings.
3. **Create `full_crew`** with all 4 agents + 4 tasks
4. **Uncomment the run block** and execute
5. **Verify** `slack_notification.txt` contains the `*SIGMA DATATECH DATA QUALITY ALERT*` header and a severity indicator

**Success criterion:** Show the trainer the Slack message. It must be 6 lines. If it is longer, your backstory is not doing its job — rewrite it and re-run.

**Reflection questions (answer at debrief):**
- Which of `role`, `goal`, `backstory` had the most effect on the output?
- For a nightly production pipeline: LangGraph or CrewAI? Why?

---

### Debrief
**What just happened:** You didn't just add code — you hired a new agent by describing who they are and what they fear. That is the CrewAI mental model: people, not nodes.

**What the agent got right:** Context passing (`context=[task_guardian]`) made the reporter's output grounded in real findings, not hallucinated DQ scores.

**What to watch for:** The Surgeon sometimes marks refunds (negative amounts) as data errors — they are legitimate business transactions. Domain knowledge is not replaceable by backstory.

**The rule:** CrewAI for stable role-based workflows. LangGraph for dynamic routing with retry loops. Neither replaces a human DQ review for financial data.

**Where this fits:** Day 11 adds LLM observability — you will see exactly what these 4-agent runs cost in Bedrock tokens and set up cost alerts.

---

## Lab 4 ★ — Self-Healing Pipeline Agent (Stretch Goal)
**Total time: ~45 minutes** (Phase A: 20 min + Phase B: 20 min + debrief: 5 min)

*Attempt after completing Labs 1–3. If time is short, do Phase A only and come back to Phase B.*

### Mission Brief
It is 2 AM. A Sigma DataTech pipeline crashes in production. Instead of paging an on-call DE, your self-healing agent catches the failure, reads the error, asks Bedrock to patch the code, re-runs it, and saves the fix to SQLite — so the next time the same error occurs, it costs zero Bedrock calls.

### What You Will Learn
- Error fingerprinting: identify recurring failures by error signature, not full text
- Safe code execution: subprocess runner with timeout and crash isolation
- Memory-informed repair: agent consults cache before every LLM call
- The critical distinction: Python runtime errors (fixable) vs logic bugs (silent, dangerous)

### Manual-First Exercise (3 minutes)
Open `4_stretch_goal_agent_memory.py`. The `BROKEN_PIPELINE` variable contains intentionally broken code. Read it carefully.

**The script says "at least 3 bugs."** Find as many as you can. Write them on paper with line numbers and exact bug descriptions. Then run the lab and check if the agent found the same ones — and whether it found one you missed.

### Pre-requisites
- Labs 1, 2, and 3 complete
- `python tests/validate_day10.py` shows all ✅

---

### Phase A — Run the Healer (20 minutes)

**Step 1** — Run the agent (first time):
```bash
python 4_stretch_goal_agent_memory.py
```
Watch: each attempt prints the error, whether it hit cache or called Bedrock, and the diagnosis. Count how many LLM calls it made.

**Step 2** — Run it again immediately:
```bash
python 4_stretch_goal_agent_memory.py
```
Watch for `[MEMORY] Known fix found! Applying from memory (no LLM call needed).` — second run should cost zero Bedrock calls for known errors.

**Step 3** — Inspect outputs:
```bash
cat agent_outputs/healing_log.json
# total_attempts, from_memory flags, final_status

cat agent_outputs/patched_pipeline.py
# compare to BROKEN_PIPELINE — confirm all bugs are fixed
```

**Step 4** — Check the memory cache:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('agent_memory.db')
for fp, err, ok, ts in conn.execute('SELECT error_fingerprint, substr(error_message,1,60), success, created_at FROM healing_history ORDER BY id DESC LIMIT 8').fetchall():
    print(f'{'✅' if ok else '❌'}  {ts[:16]}  fp={fp}  {err}...')
conn.close()
"
```

**Step 5** — Answer the judgment question about the biggest risk of auto-patching in production.

**Validation:**
- `healing_log.json` exists, `"final_status": "success"`
- `patched_pipeline.py` exists and contains the fixed code
- Second run shows `"from_memory": true` in the log
- Confirm how many bugs the agent found — was it 3 or 4?

---

### Phase B — Build Task: Test the Healer's Limits (20 minutes)

**The core hypothesis to test:** Self-healing agents fix Python runtime errors (traceback = clear signal). They cannot fix silent logic bugs (code runs, answer is wrong, no exception raised).

Open `4_stretch_goal_agent_memory.py`, scroll to `student_build_task()`. Steps 1–5:

1. **Write `BROKEN_PIPELINE_V2`** — a multi-line string with your own broken pipeline using the Sigma DataTech schema. Must include: 2 Python runtime bugs AND 1 SQL logic bug that produces wrong results but no exception (e.g., wrong filter before a GROUP BY, missing NULL exclusion, incorrect date range)
2. **Run the healer against your pipeline** — uncomment the Step 2 block
3. **Inspect `healing_log_v2.json`** — which bugs did it catch?
4. **Run it a second time** — how many LLM calls this time? Explain why.
5. **Answer the reflection questions** — which bug did it miss, and how would you catch it in production?

**The expected finding:** The healer fixes your Python bugs. It declares success even though the logic bug remains. That is the lesson. The question to answer: how do you catch the logic bug if the healer can't?

**Show the trainer:** `healing_log_v2.json` + your answer to "what did the agent miss and how would you catch it in production?"

---

### Debrief
**What just happened:** The healer used MD5 fingerprinting on the last 3 error lines. Same error class + same call location = same fingerprint = cache hit. First run: paid for LLM calls. Second run: zero cost.

**What the agent got right:** Subprocess isolation — when the broken pipeline crashes, the healer never crashes. Clean escalation when `MAX_HEAL_ATTEMPTS` is hit.

**What to watch for:** The agent produced a plausible-looking fix for your logic bug — the code runs, the output looks reasonable, but the numbers are wrong. That is the most dangerous failure mode in production AI pipelines. Silent wrong data is worse than a crash.

**The rule:** Self-healing is a reliability win for infrastructure failures. It is NOT a substitute for data quality checks, unit tests, and human review for anything that touches financial aggregations.

**Where this fits:** Day 11 adds LLM observability — you will see exactly how many Bedrock calls Labs 1–4 made and what they cost, and make the cache savings visible in a dashboard.

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
