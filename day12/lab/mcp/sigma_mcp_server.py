"""
Sigma MCP Server — Lambda Function
Exposes all 9 platform tools as discoverable MCP-style resources.

The Bedrock Supervisor Agent queries GET /tools at runtime to discover
what capabilities are available. This is the key MCP insight:
agents do NOT need to know their tools at build time.

Deploy this as a Lambda function with a Function URL enabled.
"""

import json, os, boto3
from datetime import datetime, timezone


# ── Tool registry ─────────────────────────────────────────────────────────────
# Each entry describes a tool: name, which Lambda it calls, what it does,
# and what parameters it accepts. Agents read this to decide which tool to use.

TOOLS = [
    {
        "name":        "check_cloudwatch_metrics",
        "lambda":      "sigma-tool-check-cloudwatch",
        "description": "Correlates Lambda version history, Firehose delivery failures, "
                       "and Kinesis throttles over a time window. "
                       "Use this first when investigating a pipeline failure.",
        "parameters": {
            "function_name": {"type": "string",  "required": False,
                              "default": "sigma-kinesis-producer",
                              "description": "Lambda function to investigate"},
            "hours_back":    {"type": "integer", "required": False, "default": 8,
                              "description": "How many hours back to look"},
        },
    },
    {
        "name":        "get_kinesis_records",
        "lambda":      "sigma-tool-get-kinesis-records",
        "description": "Replays records from a Kinesis shard starting at a specific timestamp. "
                       "Applies field remapping to fix broken producer output. "
                       "Use when you need to recover records that did not reach Snowflake.",
        "parameters": {
            "stream_name":        {"type": "string",  "required": False},
            "shard_id":           {"type": "string",  "required": False,
                                   "default": "shardId-000000000000"},
            "start_timestamp":    {"type": "string",  "required": False,
                                   "description": "ISO timestamp for replay start"},
            "already_loaded_ids": {"type": "string",  "required": False,
                                   "default": "[]",
                                   "description": "JSON array of transaction_ids already in Snowflake"},
        },
    },
    {
        "name":        "query_snowflake",
        "lambda":      "sigma-tool-query-snowflake",
        "description": "Executes SQL against Snowflake and returns results as JSON. "
                       "Use to calculate GMV gaps, verify row counts, check for duplicates.",
        "parameters": {
            "sql":       {"type": "string",  "required": True},
            "warehouse": {"type": "string",  "required": False},
            "max_rows":  {"type": "integer", "required": False, "default": 500},
        },
    },
    {
        "name":        "rollback_lambda_version",
        "lambda":      "sigma-tool-rollback-lambda",
        "description": "Rolls back a Lambda alias to the previous stable version. "
                       "Sends 5 test records to verify the rollback worked. "
                       "Use after root cause is confirmed as a bad Lambda deploy.",
        "parameters": {
            "function_name":  {"type": "string", "required": False,
                               "default": "sigma-kinesis-producer"},
            "alias_name":     {"type": "string", "required": False, "default": "LIVE"},
            "target_version": {"type": "string", "required": False, "default": "previous"},
        },
    },
    {
        "name":        "create_cloudwatch_alarm",
        "lambda":      "sigma-tool-create-alarm",
        "description": "Creates a CloudWatch metric alarm that goes live immediately. "
                       "Use AFTER recovery to harden the pipeline against this failure repeating. "
                       "Available alarm_types: zero_snowflake_load, lambda_version_change, pipeline_row_divergence",
        "parameters": {
            "alarm_type":   {"type": "string", "required": True,
                             "enum": ["zero_snowflake_load",
                                      "lambda_version_change",
                                      "pipeline_row_divergence"]},
            "sns_topic_arn": {"type": "string", "required": False},
        },
    },
    {
        "name":        "quarantine_rows",
        "lambda":      "sigma-tool-quarantine-rows",
        "description": "Writes failed records to S3 quarantine/ with a reason tag. "
                       "Use for records that cannot be loaded to Snowflake. "
                       "Quarantine preserves records — they are NOT deleted.",
        "parameters": {
            "records":           {"type": "string",  "required": True,
                                  "description": "JSON array of record dicts"},
            "quarantine_reason": {"type": "string",  "required": True},
            "source_context":    {"type": "string",  "required": False},
        },
    },
    {
        "name":        "load_to_snowflake",
        "lambda":      "sigma-tool-load-snowflake",
        "description": "Bulk loads clean records to Snowflake using MERGE INTO. "
                       "Idempotent — loading the same transaction_id twice is safe. "
                       "Use after quarantining bad rows.",
        "parameters": {
            "records":    {"type": "string", "required": True,
                           "description": "JSON array of clean record dicts"},
            "table_name": {"type": "string", "required": False},
        },
    },
    {
        "name":        "write_incident_report",
        "lambda":      "sigma-tool-write-report",
        "description": "Compiles all agent findings into a structured post-mortem. "
                       "Writes markdown to S3 reports/. Call this last, after all other agents complete.",
        "parameters": {
            "findings": {"type": "string", "required": True,
                         "description": "JSON object with forensics, impact, recovery, rollback, hardening findings"},
        },
    },
    {
        "name":        "send_sns_alert",
        "lambda":      "sigma-tool-send-alert",
        "description": "Publishes an alert to the SNS topic. "
                       "Subscribers receive it as an email. "
                       "Use when an SLA breach is confirmed or when the pipeline is restored.",
        "parameters": {
            "message":   {"type": "string", "required": True},
            "severity":  {"type": "string", "required": False,
                          "enum": ["critical", "high", "medium", "info"]},
        },
    },
]


def lambda_handler(event, context):
    """
    Routes HTTP requests from Lambda Function URL.
    GET  /tools           → return tool registry
    POST /call/{tool}     → invoke the corresponding Lambda function
    GET  /health          → health check
    """
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path   = event.get("rawPath", "/")

    if path == "/health":
        return _response(200, {
            "status":    "ok",
            "tools":     len(TOOLS),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    if path == "/tools" and method == "GET":
        return _response(200, {
            "tools": TOOLS,
            "count": len(TOOLS),
            "description": "Sigma DataTech Platform Tools — discoverable at runtime via MCP",
        })

    if path.startswith("/call/") and method == "POST":
        tool_name = path.replace("/call/", "").strip("/")
        tool      = next((t for t in TOOLS if t["name"] == tool_name), None)
        if not tool:
            return _response(404, {
                "error": f"Tool '{tool_name}' not found",
                "available": [t["name"] for t in TOOLS],
            })
        body   = json.loads(event.get("body", "{}") or "{}")
        result = invoke_tool(tool, body)
        return _response(200, result)

    return _response(404, {"error": f"Unknown path: {path}"})


def invoke_tool(tool: dict, params: dict) -> dict:
    """Invoke the Lambda function for this tool."""
    lam    = boto3.client("lambda",
                          region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    payload = {
        "actionGroup": "DataPlatformTools",
        "function":    tool["name"],
        "parameters":  [{"name": k, "value": str(v)} for k, v in params.items()],
    }
    try:
        resp    = lam.invoke(
            FunctionName=tool["lambda"],
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode(),
        )
        result  = json.loads(resp["Payload"].read())
        body    = result.get("response", {}) \
                        .get("functionResponse", {}) \
                        .get("responseBody", {}) \
                        .get("TEXT", {}) \
                        .get("body", "{}")
        return {"tool": tool["name"], "result": json.loads(body)}
    except Exception as e:
        return {"tool": tool["name"], "error": str(e)}


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers":    {"Content-Type": "application/json"},
        "body":       json.dumps(body, default=str),
    }
