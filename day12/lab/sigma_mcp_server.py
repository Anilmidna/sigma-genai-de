"""
==============================================================================
SIGMA INTELLIGENCE PLATFORM — MCP TOOL SERVER
==============================================================================
FastAPI-based tool server running on port 8005.
Exposes the data platform as discoverable tools.

The supervisor agent discovers these tools at RUNTIME — not at build time.
Add a new tool here → supervisor automatically finds and uses it.
That is the MCP value proposition.

Tools exposed:
  - list_s3_files         : list latest files in S3 prefix
  - read_s3_file          : read a specific S3 file
  - query_snowflake       : run a SQL query (returns results as JSON)
  - send_alert            : send platform alert (log + optional Slack)
  - get_agent_memory      : query ChromaDB RAG memory
  - save_agent_memory     : save to ChromaDB RAG memory
  - trigger_databricks    : trigger a Databricks job via REST API

Endpoints:
  GET  /tools             : list all available tools (supervisor calls this)
  POST /call/{tool_name}  : execute a specific tool
  GET  /health            : health check
==============================================================================
"""

import boto3, json, logging, os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any

# Import shared memory
import sys
sys.path.insert(0, os.path.dirname(__file__))
from agent_memory import AgentMemory

app    = FastAPI(title="Sigma MCP Tool Server", version="1.0")
memory = AgentMemory()
logger = logging.getLogger("mcp-server")
logging.basicConfig(level=logging.INFO,
                    format="[%(asctime)s] [mcp-server] %(levelname)s — %(message)s",
                    datefmt="%H:%M:%S")

REGION   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
LOG_FILE = os.getenv("PLATFORM_DIR", os.path.dirname(__file__)) + "/logs/alerts.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# ── Tool registry ─────────────────────────────────────────────────────────────
# Each tool has name, description, parameters schema.
# Supervisor discovers this list at runtime via GET /tools.

TOOL_REGISTRY = [
    {
        "name":        "list_s3_files",
        "description": "List the latest files in an S3 bucket under a given prefix",
        "parameters": {
            "bucket": {"type": "string", "required": True},
            "prefix": {"type": "string", "required": True},
            "max_files": {"type": "integer", "required": False, "default": 5},
        },
    },
    {
        "name":        "read_s3_file",
        "description": "Read and return the content of a specific S3 file (JSON/GZIP)",
        "parameters": {
            "bucket": {"type": "string", "required": True},
            "key":    {"type": "string", "required": True},
        },
    },
    {
        "name":        "query_snowflake",
        "description": "Execute a SQL query against Snowflake and return results as JSON",
        "parameters": {
            "sql":       {"type": "string",  "required": True},
            "warehouse": {"type": "string",  "required": False, "default": "SIGMA_WH"},
            "max_rows":  {"type": "integer", "required": False, "default": 100},
        },
    },
    {
        "name":        "send_alert",
        "description": "Send a platform alert. Logs to file. Optionally sends to Slack.",
        "parameters": {
            "message":  {"type": "string", "required": True},
            "severity": {"type": "string", "required": False, "default": "info"},
        },
    },
    {
        "name":        "get_agent_memory",
        "description": "Query ChromaDB RAG memory for similar past incidents",
        "parameters": {
            "collection": {"type": "string", "required": True,
                           "enum": ["schema_drift", "pii_findings", "quality_issues"]},
            "query":      {"type": "string",  "required": True},
            "n_results":  {"type": "integer", "required": False, "default": 3},
        },
    },
    {
        "name":        "save_agent_memory",
        "description": "Save an incident or finding to ChromaDB RAG memory",
        "parameters": {
            "collection": {"type": "string", "required": True},
            "doc_id":     {"type": "string", "required": True},
            "content":    {"type": "string", "required": True},
            "metadata":   {"type": "object", "required": False},
        },
    },
    {
        "name":        "trigger_databricks",
        "description": "Trigger a Databricks job via REST API and return job run ID",
        "parameters": {
            "job_name":       {"type": "string", "required": True},
            "notebook_params":{"type": "object", "required": False},
        },
    },
]

# ── Tool implementations ──────────────────────────────────────────────────────

def tool_list_s3_files(params: dict) -> dict:
    import gzip
    s3       = boto3.client("s3", region_name=REGION)
    bucket   = params["bucket"]
    prefix   = params["prefix"]
    max_files= params.get("max_files", 5)
    resp     = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    objects  = resp.get("Contents", [])
    objects  = sorted(objects, key=lambda x: x["LastModified"], reverse=True)[:max_files]
    files    = [{"key": o["Key"], "size": o["Size"],
                 "last_modified": o["LastModified"].isoformat()} for o in objects]
    return {"bucket": bucket, "prefix": prefix, "files": files, "count": len(files)}

def tool_read_s3_file(params: dict) -> dict:
    import gzip
    s3  = boto3.client("s3", region_name=REGION)
    obj = s3.get_object(Bucket=params["bucket"], Key=params["key"])
    try:
        data = gzip.decompress(obj["Body"].read()).decode("utf-8")
        rows = [json.loads(line) for line in data.strip().splitlines() if line.strip()]
        return {"key": params["key"], "rows": len(rows), "sample": rows[:3]}
    except Exception:
        content = obj["Body"].read().decode("utf-8")
        return {"key": params["key"], "content": content[:500]}

def tool_query_snowflake(params: dict) -> dict:
    """
    Execute SQL against Snowflake.
    Requires SNOWFLAKE_* env vars to be set in .env
    """
    try:
        import snowflake.connector
        conn = snowflake.connector.connect(
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            database=os.getenv("SNOWFLAKE_DATABASE", "SIGMA"),
            warehouse=params.get("warehouse", os.getenv("SNOWFLAKE_WAREHOUSE", "SIGMA_WH")),
        )
        cur  = conn.cursor()
        cur.execute(params["sql"])
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchmany(params.get("max_rows", 100))]
        conn.close()
        return {"sql": params["sql"], "row_count": len(rows), "columns": cols, "data": rows}
    except ImportError:
        return {"error": "snowflake-connector-python not installed",
                "hint": "pip install snowflake-connector-python"}
    except Exception as e:
        return {"error": str(e), "sql": params["sql"]}

def tool_send_alert(params: dict) -> dict:
    """
    Log alert to file. In production: also post to Slack via webhook.
    """
    message  = params["message"]
    severity = params.get("severity", "info").upper()
    ts       = datetime.now().isoformat()
    log_line = f"[{ts}] [{severity}] {message}\n"

    with open(LOG_FILE, "a") as f:
        f.write(log_line)

    logger.info(f"ALERT [{severity}]: {message}")

    # Slack webhook (optional — set SLACK_WEBHOOK_URL in .env)
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    slack_sent = False
    if slack_url:
        try:
            import urllib.request
            payload = json.dumps({"text": f"[{severity}] {message}"}).encode()
            req     = urllib.request.Request(slack_url, data=payload,
                                             headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
            slack_sent = True
        except Exception:
            pass

    return {"status": "sent", "severity": severity,
            "logged_to": LOG_FILE, "slack_sent": slack_sent}

def tool_get_agent_memory(params: dict) -> dict:
    results = memory.retrieve(params["collection"], params["query"],
                              params.get("n_results", 3))
    return {"collection": params["collection"], "query": params["query"],
            "results": results, "count": len(results)}

def tool_save_agent_memory(params: dict) -> dict:
    success = memory.save(params["collection"], params["doc_id"],
                          params["content"], params.get("metadata"))
    return {"status": "saved" if success else "failed",
            "collection": params["collection"], "doc_id": params["doc_id"]}

def tool_trigger_databricks(params: dict) -> dict:
    """
    Trigger Databricks job via REST API.
    Requires DATABRICKS_HOST and DATABRICKS_TOKEN in .env
    """
    try:
        import urllib.request, urllib.error
        host  = os.getenv("DATABRICKS_HOST")
        token = os.getenv("DATABRICKS_TOKEN")
        if not host or not token:
            return {"error": "DATABRICKS_HOST and DATABRICKS_TOKEN not set in .env"}

        # Find job by name
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url     = f"{host}/api/2.1/jobs/list"
        req     = urllib.request.Request(url, headers=headers)
        resp    = json.loads(urllib.request.urlopen(req, timeout=10).read())
        jobs    = resp.get("jobs", [])
        job     = next((j for j in jobs if j["settings"]["name"] == params["job_name"]), None)
        if not job:
            return {"error": f"Job '{params['job_name']}' not found",
                    "available_jobs": [j["settings"]["name"] for j in jobs]}

        # Trigger the job
        run_payload = {"job_id": job["job_id"],
                       "notebook_params": params.get("notebook_params", {})}
        run_url     = f"{host}/api/2.1/jobs/run-now"
        run_req     = urllib.request.Request(run_url,
                          data=json.dumps(run_payload).encode(),
                          headers=headers)
        run_resp    = json.loads(urllib.request.urlopen(run_req, timeout=10).read())
        return {"status": "triggered", "job_name": params["job_name"],
                "run_id": run_resp.get("run_id")}
    except Exception as e:
        return {"error": str(e)}

# ── Tool dispatch ─────────────────────────────────────────────────────────────
TOOL_HANDLERS = {
    "list_s3_files":    tool_list_s3_files,
    "read_s3_file":     tool_read_s3_file,
    "query_snowflake":  tool_query_snowflake,
    "send_alert":       tool_send_alert,
    "get_agent_memory": tool_get_agent_memory,
    "save_agent_memory":tool_save_agent_memory,
    "trigger_databricks":tool_trigger_databricks,
}

# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/tools")
def list_tools():
    """
    Supervisor calls this at startup to discover what tools exist.
    Add a new tool to TOOL_REGISTRY + TOOL_HANDLERS → supervisor auto-discovers it.
    """
    return {"tools": TOOL_REGISTRY, "count": len(TOOL_REGISTRY)}

class ToolCallRequest(BaseModel):
    params: dict[str, Any] = {}

@app.post("/call/{tool_name}")
async def call_tool(tool_name: str, req: ToolCallRequest):
    """Execute a specific tool by name."""
    if tool_name not in TOOL_HANDLERS:
        raise HTTPException(status_code=404,
            detail=f"Tool '{tool_name}' not found. Available: {list(TOOL_HANDLERS.keys())}")
    try:
        logger.info(f"Executing tool: {tool_name} | params: {req.params}")
        result = TOOL_HANDLERS[tool_name](req.params)
        return {"tool": tool_name, "status": "success", "result": result,
                "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {
        "status":      "ok",
        "service":     "sigma-mcp-server",
        "tools":       len(TOOL_REGISTRY),
        "memory":      memory.summary(),
        "timestamp":   datetime.now().isoformat(),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005, log_level="info")
