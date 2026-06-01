"""
==============================================================================
SIGMA INTELLIGENCE PLATFORM — SUPERVISOR AGENT
FastAPI app running on port 8001
==============================================================================
Receives pipeline trigger events. Discovers available tools via MCP server.
Calls all 3 specialist agents in parallel. Consolidates results.
Makes final load decision. Sends alert if needed.

Endpoints:
  POST /trigger    — trigger full pipeline for a new S3 file
  GET  /health     — health check
  GET  /status     — last pipeline run status
==============================================================================
"""

import asyncio, httpx, json, os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from utils import call_bedrock_lite, get_logger, get_latest_s3_file, parse_json_response

app    = FastAPI(title="Sigma Supervisor Agent", version="1.0")
logger = get_logger("supervisor")

# ── Config from environment ───────────────────────────────────────────────────
REGION        = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
S3_BUCKET     = os.getenv("SIGMA_S3_BUCKET", "sigma-datatech-team")
MCP_SERVER    = os.getenv("MCP_SERVER_URL", "http://localhost:8005")
SCHEMA_AGENT  = os.getenv("SCHEMA_AGENT_URL", "http://localhost:8002")
PII_AGENT     = os.getenv("PII_AGENT_URL",    "http://localhost:8003")
QUALITY_AGENT = os.getenv("QUALITY_AGENT_URL","http://localhost:8004")
OUTPUT_DIR    = os.getenv("PLATFORM_DIR", os.path.dirname(__file__)) + "/agent_outputs"

os.makedirs(OUTPUT_DIR, exist_ok=True)
last_run_status = {"status": "never_run", "timestamp": None}

# ── Request/Response models ───────────────────────────────────────────────────
class TriggerRequest(BaseModel):
    bucket: str = S3_BUCKET
    prefix: str = "bronze/transactions/"
    mode:   str = "full"   # full / schema_only / pii_only / quality_only

class TriggerResponse(BaseModel):
    run_id:        str
    timestamp:     str
    bucket:        str
    file_processed: str | None
    agents_called: list[str]
    schema_result: dict
    pii_result:    dict
    quality_result:dict
    load_decision: str
    alert_fired:   bool
    duration_sec:  float

# ── MCP tool discovery ────────────────────────────────────────────────────────
async def discover_mcp_tools() -> list[str]:
    """
    Discover available tools from MCP server at runtime.
    Key insight: supervisor does NOT need to know tools at build time.
    Add a new tool to MCP server → supervisor auto-discovers it.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{MCP_SERVER}/tools")
            if resp.status_code == 200:
                tools = resp.json().get("tools", [])
                logger.info(f"MCP tools discovered: {[t['name'] for t in tools]}")
                return tools
    except Exception as e:
        logger.warning(f"MCP server unavailable: {e}. Continuing without tool discovery.")
    return []

async def call_mcp_tool(tool_name: str, params: dict) -> dict:
    """Call a specific tool on the MCP server."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{MCP_SERVER}/call/{tool_name}", json=params)
            return resp.json()
    except Exception as e:
        logger.error(f"MCP tool call failed ({tool_name}): {e}")
        return {"error": str(e)}

# ── Call specialist agents in parallel ───────────────────────────────────────
async def call_agent(agent_url: str, endpoint: str, payload: dict,
                     agent_name: str, timeout: float = 120.0) -> dict:
    """Call a specialist agent via HTTP POST."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info(f"Calling {agent_name}...")
            resp = await client.post(f"{agent_url}/{endpoint}", json=payload)
            result = resp.json()
            logger.info(f"{agent_name} done — status: {result.get('status','?')}")
            return result
    except Exception as e:
        logger.error(f"{agent_name} failed: {e}")
        return {"status": "error", "error": str(e), "agent": agent_name}

# ── Supervisor routing decision ───────────────────────────────────────────────
async def make_routing_decision(file_key: str, tools: list) -> dict:
    """
    Ask LLM (Nova Lite — cheap) which agents to run for this file.
    This is the supervisor pattern: central router decides specialist assignment.
    """
    tool_names = [t["name"] for t in tools] if tools else ["schema", "pii", "quality"]
    prompt = f"""You are the supervisor agent for Sigma DataTech's data platform.

A new file arrived: {file_key}
Available specialist agents: schema_evolution, pii_detection, ingestion_quality
Available MCP tools: {tool_names}

Decide which agents to run. For a new transaction file always run all three.
Respond in JSON only:
{{
  "agents": ["schema_evolution", "pii_detection", "ingestion_quality"],
  "execution": "parallel",
  "reasoning": "one sentence"
}}"""
    response = call_bedrock_lite(prompt, REGION)
    result   = parse_json_response(response)
    if not result:
        result = {
            "agents": ["schema_evolution", "pii_detection", "ingestion_quality"],
            "execution": "parallel",
            "reasoning": "Default: run all agents for new transaction file",
        }
    return result

# ── Main pipeline trigger ─────────────────────────────────────────────────────
@app.post("/trigger", response_model=TriggerResponse)
async def trigger_pipeline(req: TriggerRequest):
    run_id    = datetime.now().strftime("RUN-%Y%m%d-%H%M%S")
    start_ts  = datetime.now()
    logger.info(f"{'='*50}")
    logger.info(f"Pipeline triggered | run_id={run_id} | bucket={req.bucket}")

    # Step 1: Get latest S3 file
    file_key = get_latest_s3_file(req.bucket, req.prefix, REGION)
    if not file_key:
        raise HTTPException(status_code=404,
            detail="No files found in S3. Run data_generator.py first and wait 60-90s for Firehose delivery.")
    logger.info(f"Processing file: {file_key}")

    # Step 2: Discover MCP tools
    mcp_tools = await discover_mcp_tools()

    # Step 3: Supervisor routing decision (Nova Lite — cheap)
    routing = await make_routing_decision(file_key, mcp_tools)
    logger.info(f"Routing: {routing['agents']} ({routing['execution']})")
    logger.info(f"Reason: {routing['reasoning']}")

    # Step 4: Call all 3 agents in PARALLEL (asyncio.gather)
    agent_payload = {"bucket": req.bucket, "file_key": file_key, "region": REGION}

    schema_task  = call_agent(SCHEMA_AGENT,  "detect-drift",   agent_payload, "SchemaAgent")
    pii_task     = call_agent(PII_AGENT,     "scan-pii",       agent_payload, "PIIAgent")
    quality_task = call_agent(QUALITY_AGENT, "check-quality",  agent_payload, "QualityAgent")

    schema_result, pii_result, quality_result = await asyncio.gather(
        schema_task, pii_task, quality_task
    )

    # Step 5: Consolidate and make load decision
    has_critical_pii  = pii_result.get("restricted_columns_found", False)
    has_drift         = schema_result.get("drift_detected", False)
    quarantine_pct    = quality_result.get("quarantine_pct", 0)
    quality_decision  = quality_result.get("load_decision", "quarantine_and_load")

    if has_critical_pii:
        load_decision = "BLOCKED — PII compliance sign-off required"
        alert_fired   = True
    elif quarantine_pct > 20:
        load_decision = "BLOCKED — quarantine rate exceeds 20% threshold"
        alert_fired   = True
    else:
        load_decision = quality_decision
        alert_fired   = has_drift or quarantine_pct > 5

    logger.info(f"Load decision: {load_decision}")
    logger.info(f"Alert required: {alert_fired}")

    # Step 6: Fire alert via MCP tool if needed
    if alert_fired and mcp_tools:
        alert_msg = (
            f"[{run_id}] Pipeline alert | "
            f"File: {file_key} | "
            f"Drift: {has_drift} | "
            f"PII blocked: {has_critical_pii} | "
            f"Quarantine: {quarantine_pct}% | "
            f"Decision: {load_decision}"
        )
        await call_mcp_tool("send_alert", {"message": alert_msg, "severity": "high"})

    # Step 7: Save consolidated report
    duration = round((datetime.now() - start_ts).total_seconds(), 2)
    report   = {
        "run_id":          run_id,
        "timestamp":       datetime.now().isoformat(),
        "bucket":          req.bucket,
        "file_processed":  file_key,
        "agents_called":   routing["agents"],
        "schema_result":   schema_result,
        "pii_result":      pii_result,
        "quality_result":  quality_result,
        "load_decision":   load_decision,
        "alert_fired":     alert_fired,
        "duration_sec":    duration,
    }

    report_path = f"{OUTPUT_DIR}/{run_id}_pipeline_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    global last_run_status
    last_run_status = {"status": "completed", "run_id": run_id,
                       "timestamp": datetime.now().isoformat(),
                       "load_decision": load_decision}

    logger.info(f"Pipeline complete | duration={duration}s | report={report_path}")
    logger.info(f"{'='*50}")
    return TriggerResponse(**report)

@app.get("/health")
def health():
    return {"status": "ok", "service": "supervisor", "timestamp": datetime.now().isoformat()}

@app.get("/status")
def status():
    return last_run_status
