"""
==============================================================================
DAY 11 — LAB 1: MULTI-AGENT ARCHITECTURES
Supervisor · Swarm · Sequential Pipeline
==============================================================================

MISSION BRIEFING
----------------
Sigma DataTech's data platform is growing. One agent doing everything is a
single point of failure — slow, fragile, hard to debug.

The engineering lead says: "We need specialist agents that collaborate."
Three patterns exist. You are going to build all three and understand WHEN
to use each one.

WHAT YOU WILL LEARN
-------------------
- Supervisor pattern: one orchestrator agent routes tasks to specialist agents
- Swarm pattern: agents pick up tasks from a shared queue (peer-to-peer)
- Sequential pipeline: output of Agent A feeds Agent B feeds Agent C
- How to route between patterns based on task complexity and data volume
- Why multi-agent systems fail (and what the guardrails look like)

MANUAL FIRST (3 minutes — no laptop)
--------------------------------------
On paper: Sigma DataTech gets a new CSV every hour. It needs to be:
  profiled → quality-checked → PII-detected → catalogued → loaded.

Draw THREE different ways to assign these tasks to 3 agents.
Which design would you use if the CSV could be 1 row OR 10 million rows?

WHERE THIS FITS
---------------
Today's labs build the full Ingestion Quality Agent using ALL THREE patterns.
Lab 1 shows you the skeleton. Lab 2 assembles it into production code.

==============================================================================
OUTPUT
------
  agent_outputs/supervisor_result.json   — supervisor routing trace
  agent_outputs/swarm_result.json        — swarm task completion trace
  agent_outputs/pipeline_result.json     — sequential pipeline trace
==============================================================================
"""

import os, sys, json, time
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import boto3
except ImportError:
    print("[ERROR] Run: pip install boto3")
    sys.exit(1)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "agent_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MODEL_ID = "amazon.nova-lite-v1:0"   # Nova Lite: fast + cheap for routing decisions
REGION   = "us-east-1"

# ── Bedrock helper ────────────────────────────────────────────────────────────
def call_bedrock(prompt: str, system: str = "", max_tokens: int = 800) -> str:
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.1},
    }
    if system:
        body["system"] = [{"text": system}]
    resp = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    return json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"].strip()

# ─────────────────────────────────────────────────────────────────────────────
# PATTERN 1: SUPERVISOR PATTERN
# One orchestrator decides which specialist agent handles the task.
# Good for: routing, load balancing, conditional specialist selection.
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("PATTERN 1: SUPERVISOR AGENT")
print("="*60)

# Simulate incoming tasks
INCOMING_TASKS = [
    {"id": "T001", "type": "new_csv",       "file": "transactions_raw.csv",  "rows": 500},
    {"id": "T002", "type": "quality_alert", "file": "customers_raw.csv",     "rows": 100},
    {"id": "T003", "type": "schema_drift",  "file": "payments_nov.csv",      "rows": 12000},
    {"id": "T004", "type": "pii_scan",      "file": "employee_records.csv",  "rows": 50},
]

# Specialist agents available to the supervisor
AGENTS = {
    "ProfilerAgent":  "Profiles new CSVs: row count, column types, null rates, basic stats",
    "QualityAgent":   "Runs Great Expectations checks, flags rows failing quality rules",
    "PIIAgent":       "Scans columns for PII: names, emails, phones, PAN, Aadhaar",
    "SchemaAgent":    "Detects schema drift, generates migration SQL, alerts on breaking changes",
    "LoaderAgent":    "Loads validated data into Snowflake staging tables",
}

def supervisor_route(task: dict) -> dict:
    """Supervisor: decide which agent(s) handle this task."""
    agent_list = "\n".join([f"- {name}: {desc}" for name, desc in AGENTS.items()])
    prompt = f"""You are a data platform supervisor at Sigma DataTech.

Available specialist agents:
{agent_list}

Incoming task:
  Task ID  : {task['id']}
  Type     : {task['type']}
  File     : {task['file']}
  Row count: {task['rows']}

Respond in JSON only (no markdown, no explanation):
{{
  "task_id": "{task['id']}",
  "assigned_agents": ["AgentName1", "AgentName2"],
  "execution_order": "parallel or sequential",
  "reasoning": "one sentence why"
}}"""

    response = call_bedrock(prompt)
    # Parse JSON robustly
    try:
        start = response.index("{")
        end   = response.rindex("}") + 1
        return json.loads(response[start:end])
    except Exception:
        return {"task_id": task["id"], "assigned_agents": ["ProfilerAgent"],
                "execution_order": "sequential", "reasoning": "parse fallback"}

supervisor_results = []
for task in INCOMING_TASKS:
    print(f"\n  Routing task {task['id']} ({task['type']}, {task['rows']} rows)...")
    routing = supervisor_route(task)
    supervisor_results.append({"task": task, "routing": routing})
    print(f"  → Assigned to: {routing.get('assigned_agents')} ({routing.get('execution_order')})")
    print(f"  → Reason: {routing.get('reasoning')}")
    time.sleep(0.3)

sup_path = os.path.join(OUTPUT_DIR, "supervisor_result.json")
with open(sup_path, "w") as f:
    json.dump({"pattern": "supervisor", "timestamp": datetime.now().isoformat(),
               "results": supervisor_results}, f, indent=2)
print(f"\n  ✓ Saved → {sup_path}")

# ─────────────────────────────────────────────────────────────────────────────
# PATTERN 2: SWARM PATTERN
# Agents pull tasks from a shared queue. No central boss.
# Good for: high-volume parallel processing, fault tolerance.
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("PATTERN 2: SWARM AGENT")
print("="*60)

# Simulate a task queue (in production: SQS, Redis, Kafka)
task_queue = [
    {"task_id": f"ROW_BATCH_{i}", "rows": list(range(i*50, (i+1)*50)),
     "assigned": False, "completed": False}
    for i in range(6)
]

def swarm_agent_work(agent_id: str, task: dict) -> dict:
    """Swarm agent: pull from queue, process, mark done."""
    # Simulate processing (in real code: actual profiling/validation)
    time.sleep(0.1)
    return {
        "agent_id":    agent_id,
        "task_id":     task["task_id"],
        "rows_processed": len(task["rows"]),
        "nulls_found": len(task["rows"]) // 10,   # simulated
        "status":      "completed",
        "timestamp":   datetime.now().isoformat(),
    }

swarm_log = []
agents = ["SwarmAgent-A", "SwarmAgent-B", "SwarmAgent-C"]

print(f"\n  {len(task_queue)} batches in queue, {len(agents)} swarm agents available")
for i, task in enumerate(task_queue):
    agent = agents[i % len(agents)]    # round-robin in this demo; real swarm uses available()
    result = swarm_agent_work(agent, task)
    swarm_log.append(result)
    print(f"  {agent} → {task['task_id']} ({result['rows_processed']} rows) ✓")

swarm_path = os.path.join(OUTPUT_DIR, "swarm_result.json")
with open(swarm_path, "w") as f:
    json.dump({"pattern": "swarm", "timestamp": datetime.now().isoformat(),
               "agents": agents, "results": swarm_log,
               "total_rows": sum(r["rows_processed"] for r in swarm_log),
               "total_nulls": sum(r["nulls_found"] for r in swarm_log)}, f, indent=2)
print(f"\n  ✓ Saved → {swarm_path}")

# ─────────────────────────────────────────────────────────────────────────────
# PATTERN 3: SEQUENTIAL PIPELINE
# Each agent adds value then passes to the next. Like an assembly line.
# Good for: dependent transformations where order matters.
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("PATTERN 3: SEQUENTIAL PIPELINE")
print("="*60)

# Simulate a new CSV arriving at Sigma DataTech
incoming_file = {
    "filename": "transactions_raw.csv",
    "row_count": 500,
    "columns": ["transaction_id","merchant_name","category","amount","currency",
                "transaction_date","status","customer_id","payment_method","merchant_city"],
    "sample_issues": ["4 blank transaction_ids", "7 null amounts", "3 negative amounts",
                      "2 invalid dates", "1 unknown currency"],
}

pipeline_trace = []

def pipeline_stage(stage_name: str, agent_role: str,
                   input_data: dict, instruction: str) -> dict:
    """One stage in the sequential pipeline."""
    prompt = f"""You are the {agent_role} in Sigma DataTech's data ingestion pipeline.

Input from previous stage:
{json.dumps(input_data, indent=2)}

Your task:
{instruction}

Respond in JSON only (no markdown). Include your findings and a "pass_to_next" dict
with the enriched context for the next agent."""

    response = call_bedrock(prompt, max_tokens=600)
    try:
        start = response.index("{")
        end   = response.rindex("}") + 1
        result = json.loads(response[start:end])
    except Exception:
        result = {"stage": stage_name, "status": "completed", "pass_to_next": input_data}

    result["_stage"] = stage_name
    result["_agent"] = agent_role
    result["_timestamp"] = datetime.now().isoformat()
    return result

print("\n  Stage 1 → Profiler Agent...")
stage1 = pipeline_stage(
    "Profile", "Profiler Agent",
    incoming_file,
    "Assess the data quality of this file. Summarize: completeness %, key issues found, recommended next action."
)
pipeline_trace.append(stage1)
print(f"  ✓ Profile complete")

print("  Stage 2 → Quality Agent...")
stage2 = pipeline_stage(
    "Validate", "Quality Agent",
    stage1.get("pass_to_next", incoming_file),
    "Based on the profile, list the top 3 quality rules that MUST pass before loading. Classify each issue as: auto-fixable, quarantine, or block-load."
)
pipeline_trace.append(stage2)
print(f"  ✓ Validation rules generated")

print("  Stage 3 → Loader Agent (decision)...")
stage3 = pipeline_stage(
    "LoadDecision", "Loader Agent",
    stage2.get("pass_to_next", incoming_file),
    "Given the quality findings, should this file be: loaded_clean, quarantined_partial, or rejected? Provide a one-line justification and the load_decision field."
)
pipeline_trace.append(stage3)
load_decision = stage3.get("load_decision", "quarantined_partial")
print(f"  ✓ Load decision: {load_decision}")

pipeline_path = os.path.join(OUTPUT_DIR, "pipeline_result.json")
with open(pipeline_path, "w") as f:
    json.dump({"pattern": "sequential_pipeline",
               "timestamp": datetime.now().isoformat(),
               "input_file": incoming_file,
               "stages": pipeline_trace,
               "final_decision": load_decision}, f, indent=2)
print(f"\n  ✓ Saved → {pipeline_path}")

# ─────────────────────────────────────────────────────────────────────────────
# JUDGMENT QUESTION (accountability gate)
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("JUDGMENT QUESTION")
print("="*60)
print("""
  Sigma DataTech's supervisor agent just routed a 10-million-row CSV
  to the QualityAgent and PIIAgent in PARALLEL.
  The PIIAgent finishes in 2 min. The QualityAgent runs for 45 min.

  One thing that could go WRONG with this parallel execution:
""")
judgment = input("  Your answer (1 sentence): ").strip() or "NOT ANSWERED"

# Append judgment to pipeline result
with open(pipeline_path) as f:
    data = json.load(f)
data["student_judgment"] = judgment
with open(pipeline_path, "w") as f:
    json.dump(data, f, indent=2)

# ── Final summary ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("LAB 1 COMPLETE — MULTI-AGENT PATTERNS SUMMARY")
print("="*60)
print("""
  SUPERVISOR  → Central router. Best when task TYPE varies.
                Risk: supervisor is a single point of failure.

  SWARM       → Peer agents pull from queue. Best for high volume.
                Risk: no central coordination = hard to debug ordering.

  SEQUENTIAL  → Assembly line. Each agent enriches context.
                Risk: one slow agent blocks the whole pipeline.

  REAL SYSTEMS use all three:
    Supervisor decides the pattern → Swarm handles batch rows
    → Sequential pipeline for each batch's enrichment steps.
""")
print(f"  Output files in: {OUTPUT_DIR}/")
print("    supervisor_result.json")
print("    swarm_result.json")
print("    pipeline_result.json")
