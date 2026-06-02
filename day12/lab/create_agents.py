#!/usr/bin/env python3
"""
create_agents.py
Auto-creates all Bedrock resources for Day 12 lab in YOUR AWS account.
Run once after deploy_tools.sh. Takes 5-8 minutes.
Writes SUPERVISOR_AGENT_ID, SUPERVISOR_ALIAS_ID, GUARDRAIL_ID to lab/.env automatically.

Usage (from repo/day12/ directory):
    python lab/create_agents.py
"""

import boto3
import io
import json
import re
import sys
import time
import zipfile
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

REGION    = "us-east-1"
MODEL_ID  = "amazon.nova-pro-v1:0"

SCRIPT_DIR = Path(__file__).parent          # repo/day12/lab/
ENV_PATH   = SCRIPT_DIR / ".env"
AGENTS_DIR = SCRIPT_DIR / "agents"

# ── Tool registry ───────────────────────────────────────────────────────────────

TOOLS = {
    "check_cloudwatch_metrics": {
        "lambda": "sigma-tool-check-cloudwatch",
        "description": "Check CloudWatch metrics for Lambda errors, Firehose delivery failures, Kinesis throttles, and Lambda version history.",
        "parameters": {
            "hours_back": {"description": "Hours to look back", "required": True, "type": "integer"},
        },
    },
    "query_snowflake": {
        "lambda": "sigma-tool-query-snowflake",
        "description": "Run a SQL query against Snowflake and return results as JSON.",
        "parameters": {
            "sql": {"description": "SQL query to execute", "required": True, "type": "string"},
        },
    },
    "get_kinesis_records": {
        "lambda": "sigma-tool-get-kinesis-records",
        "description": "Replay records from Kinesis shard from a given timestamp with field remapping applied.",
        "parameters": {
            "start_timestamp": {"description": "ISO timestamp to start replay from", "required": True, "type": "string"},
            "already_loaded_ids": {"description": "Comma-separated transaction_ids already in Snowflake (dedup)", "required": False, "type": "string"},
        },
    },
    "rollback_lambda_version": {
        "lambda": "sigma-tool-rollback-lambda",
        "description": "Roll back a Lambda alias to the previous stable version and verify with test records.",
        "parameters": {
            "function_name": {"description": "Lambda function name", "required": True, "type": "string"},
            "alias_name": {"description": "Lambda alias to update, e.g. LIVE", "required": True, "type": "string"},
            "target_version": {"description": "Version to roll back to, or 'previous' for auto-detect", "required": True, "type": "string"},
        },
    },
    "create_cloudwatch_alarm": {
        "lambda": "sigma-tool-create-alarm",
        "description": "Create a CloudWatch metric alarm in the current AWS account.",
        "parameters": {
            "alarm_type": {"description": "Alarm template to use: zero_snowflake_load | lambda_version_change | pipeline_row_divergence", "required": True, "type": "string"},
            "sns_topic_arn": {"description": "SNS topic ARN for alarm notifications", "required": False, "type": "string"},
        },
    },
    "quarantine_rows": {
        "lambda": "sigma-tool-quarantine-rows",
        "description": "Write rejected records to S3 quarantine/ with a reason tag.",
        "parameters": {
            "records": {"description": "JSON array of records to quarantine", "required": True, "type": "string"},
            "quarantine_reason": {"description": "Reason, e.g. null_transaction_id", "required": True, "type": "string"},
        },
    },
    "load_to_snowflake": {
        "lambda": "sigma-tool-load-snowflake",
        "description": "Bulk load records to Snowflake using MERGE INTO on transaction_id (idempotent).",
        "parameters": {
            "records": {"description": "JSON array of records to load", "required": True, "type": "string"},
        },
    },
    "write_incident_report": {
        "lambda": "sigma-tool-write-report",
        "description": "Write a structured incident post-mortem report to S3 reports/.",
        "parameters": {
            "findings": {"description": "JSON object with all agent findings", "required": True, "type": "string"},
        },
    },
    "send_sns_alert": {
        "lambda": "sigma-tool-send-alert",
        "description": "Publish an alert to the sigma-alerts SNS topic.",
        "parameters": {
            "message": {"description": "Alert message text", "required": True, "type": "string"},
            "severity": {"description": "low / medium / high / critical", "required": True, "type": "string"},
        },
    },
}

AGENT_TOOLS = {
    "ForensicsAgent":      ["check_cloudwatch_metrics", "query_snowflake"],
    "ImpactAgent":         ["query_snowflake"],
    "RecoveryAgent":       ["get_kinesis_records", "query_snowflake", "quarantine_rows", "load_to_snowflake"],
    "RollbackAgent":       ["rollback_lambda_version", "send_sns_alert"],
    "HardeningAgent":      ["create_cloudwatch_alarm", "send_sns_alert"],
    "IncidentReportAgent": ["write_incident_report", "send_sns_alert"],
    "SupervisorAgent":     list(TOOLS.keys()),
}

INSTRUCTION_FILES = {
    "ForensicsAgent":      "forensics_instructions.md",
    "ImpactAgent":         "impact_instructions.md",
    "RecoveryAgent":       "recovery_instructions.md",
    "RollbackAgent":       "rollback_instructions.md",
    "HardeningAgent":      "hardening_instructions.md",
    "IncidentReportAgent": "incident_report_instructions.md",
    "SupervisorAgent":     "supervisor_instructions.md",
}

SUB_AGENTS = [
    "ForensicsAgent", "ImpactAgent", "RecoveryAgent",
    "RollbackAgent",  "HardeningAgent", "IncidentReportAgent",
]

COLLAB_INSTRUCTIONS = {
    "ForensicsAgent":      "Investigate the pipeline failure root cause. Return structured forensics findings: root cause, failure timestamp, and records gap.",
    "ImpactAgent":         "Calculate business impact of the failure. Query Snowflake for GMV gap and check SLA contracts. Return breach status and notification requirement.",
    "RecoveryAgent":       "Replay missing records from Kinesis to Snowflake. Only call AFTER RollbackAgent confirms stable. Return rows loaded and quarantine count.",
    "RollbackAgent":       "Roll back the broken Lambda version. Call BEFORE RecoveryAgent. Return rollback status and whether recovery is cleared to proceed.",
    "HardeningAgent":      "Create 3 CloudWatch alarms based on Forensics findings to prevent recurrence. Return alarm names and creation status.",
    "IncidentReportAgent": "Compile all findings into a CTO-ready post-mortem. Write to S3 and send SNS alert. Return report S3 path.",
}

# ── Dispatcher Lambda source ────────────────────────────────────────────────────
# This Lambda sits between Bedrock agents and the tool Lambdas.
# Bedrock calls this dispatcher; dispatcher calls the correct tool Lambda.

DISPATCHER_SOURCE = '''
import boto3
import json

TOOL_MAP = {
    "check_cloudwatch_metrics": "sigma-tool-check-cloudwatch",
    "query_snowflake":           "sigma-tool-query-snowflake",
    "get_kinesis_records":       "sigma-tool-get-kinesis-records",
    "rollback_lambda_version":   "sigma-tool-rollback-lambda",
    "create_cloudwatch_alarm":   "sigma-tool-create-alarm",
    "quarantine_rows":           "sigma-tool-quarantine-rows",
    "load_to_snowflake":         "sigma-tool-load-snowflake",
    "write_incident_report":     "sigma-tool-write-report",
    "send_sns_alert":            "sigma-tool-send-alert",
}


def lambda_handler(event, context):
    function_name = event.get("function", "")
    parameters    = {p["name"]: p["value"] for p in event.get("parameters", [])}
    action_group  = event.get("actionGroup", "")

    target = TOOL_MAP.get(function_name)
    if not target:
        body = json.dumps({"error": f"Unknown function: {function_name}"})
    else:
        lc   = boto3.client("lambda")
        resp = lc.invoke(FunctionName=target, Payload=json.dumps(parameters))
        body = resp["Payload"].read().decode("utf-8")

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": action_group,
            "function": function_name,
            "functionResponse": {
                "responseBody": {"TEXT": {"body": body}}
            },
        },
    }
'''

# ── Helpers ─────────────────────────────────────────────────────────────────────

def log(msg):
    print(msg, flush=True)


def load_env():
    env = {}
    if not ENV_PATH.exists():
        return env
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def update_env(updates):
    content = ENV_PATH.read_text() if ENV_PATH.exists() else ""
    for key, val in updates.items():
        pattern = rf"^{re.escape(key)}\s*=.*$"
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, f"{key}={val}", content, flags=re.MULTILINE)
        else:
            content = content.rstrip("\n") + f"\n{key}={val}\n"
    ENV_PATH.write_text(content)


def wait_for_agent(client, agent_id, desired, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get_agent(agentId=agent_id)["agent"]["agentStatus"]
        if status == desired:
            return
        if "FAILED" in status or "DELETE" in status:
            raise RuntimeError(f"Agent {agent_id} in unexpected state: {status}")
        time.sleep(6)
    raise TimeoutError(f"Agent {agent_id} did not reach {desired} within {timeout}s")


def find_agent_by_name(client, name):
    resp = client.list_agents(maxResults=100)
    for a in resp.get("agentSummaries", []):
        if a["agentName"] == name:
            return a["agentId"]
    return None


def find_alias(client, agent_id, alias_name):
    resp = client.list_agent_aliases(agentId=agent_id, maxResults=100)
    for a in resp.get("agentAliasSummaries", []):
        if a["agentAliasName"] == alias_name:
            return a["agentAliasId"]
    return None


def build_functions(tool_names):
    functions = []
    for t_name in tool_names:
        t = TOOLS[t_name]
        functions.append({
            "name": t_name,
            "description": t["description"],
            "parameters": {
                p_name: {
                    "description": p["description"],
                    "required": p["required"],
                    "type": p["type"],
                }
                for p_name, p in t["parameters"].items()
            },
        })
    return functions


# ── Step 1: Dispatcher Lambda ───────────────────────────────────────────────────

def deploy_dispatcher(lc, role_arn, account_id):
    func_name = "sigma-bedrock-dispatcher"
    log(f"\n[1/9] Deploying {func_name}...")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dispatcher.py", DISPATCHER_SOURCE)
    zip_bytes = buf.getvalue()

    try:
        lc.get_function(FunctionName=func_name)
        lc.update_function_code(FunctionName=func_name, ZipFile=zip_bytes)
        log("  Updated.")
    except lc.exceptions.ResourceNotFoundException:
        lc.create_function(
            FunctionName=func_name,
            Runtime="python3.12",
            Role=role_arn,
            Handler="dispatcher.lambda_handler",
            Code={"ZipFile": zip_bytes},
            Timeout=120,
            MemorySize=256,
        )
        waiter = lc.get_waiter("function_active")
        waiter.wait(FunctionName=func_name)
        log("  Created.")

    # Allow Bedrock to invoke this Lambda
    try:
        lc.add_permission(
            FunctionName=func_name,
            StatementId="allow-bedrock-invoke",
            Action="lambda:InvokeFunction",
            Principal="bedrock.amazonaws.com",
            SourceAccount=account_id,
        )
    except lc.exceptions.ResourceConflictException:
        pass  # permission already exists

    dispatcher_arn = f"arn:aws:lambda:{REGION}:{account_id}:function:{func_name}"
    log(f"  ARN: {dispatcher_arn}")
    return dispatcher_arn


# ── Step 2: Guardrail ───────────────────────────────────────────────────────────

def get_or_create_guardrail(bedrock):
    log("\n[2/9] Setting up Guardrail...")
    resp = bedrock.list_guardrails(maxResults=100)
    for g in resp.get("guardrails", []):
        if g["name"] == "sigma-platform-guardrail":
            log(f"  Already exists: {g['id']}")
            return g["id"]

    r = bedrock.create_guardrail(
        name="sigma-platform-guardrail",
        description="PII redaction + destructive SQL blocking for Sigma DataTech",
        topicPolicyConfig={
            "topicsConfig": [{
                "name": "destructive-sql",
                "definition": "SQL that destroys or removes data: DROP TABLE, DELETE FROM, TRUNCATE TABLE",
                "examples": ["DROP TABLE transactions", "DELETE FROM SIGMA.SILVER.TRANSACTIONS"],
                "type": "DENY",
            }]
        },
        sensitiveInformationPolicyConfig={
            "piiEntitiesConfig": [
                {"type": "PHONE", "action": "ANONYMIZE"},
                {"type": "EMAIL", "action": "ANONYMIZE"},
                {"type": "CREDIT_DEBIT_CARD_NUMBER", "action": "ANONYMIZE"},
            ]
        },
        blockedInputMessaging="Request blocked by Sigma DataTech platform guardrail.",
        blockedOutputsMessaging="Response blocked by Sigma DataTech platform guardrail.",
    )
    guardrail_id = r["guardrailId"]
    log(f"  Created: {guardrail_id}")
    return guardrail_id


# ── Steps 3-8: Sub-agents ───────────────────────────────────────────────────────

def get_or_create_sub_agent(bedrock, name, dispatcher_arn, guardrail_id, account_id):
    instructions = (AGENTS_DIR / INSTRUCTION_FILES[name]).read_text()
    tool_names   = AGENT_TOOLS[name]

    existing_id = find_agent_by_name(bedrock, name)
    if existing_id:
        log(f"  Already exists: {existing_id}")
        alias_id = find_alias(bedrock, existing_id, "v1")
        if alias_id:
            alias_arn = f"arn:aws:bedrock:{REGION}:{account_id}:agent-alias/{existing_id}/{alias_id}"
            return existing_id, alias_id, alias_arn
        # Alias missing — prepare and create
        bedrock.prepare_agent(agentId=existing_id)
        wait_for_agent(bedrock, existing_id, "PREPARED")
        a = bedrock.create_agent_alias(agentId=existing_id, agentAliasName="v1")
        return existing_id, a["agentAlias"]["agentAliasId"], a["agentAlias"]["agentAliasArn"]

    # Create agent
    r = bedrock.create_agent(
        agentName=name,
        foundationModel=MODEL_ID,
        instruction=instructions,
        description=f"Sigma Intelligence Platform — {name}",
        idleSessionTTLInSeconds=1800,
        guardrailConfiguration={"guardrailIdentifier": guardrail_id, "guardrailVersion": "DRAFT"},
    )
    agent_id = r["agent"]["agentId"]
    log(f"  Agent ID: {agent_id}")
    time.sleep(3)

    # Action group
    bedrock.create_agent_action_group(
        agentId=agent_id,
        agentVersion="DRAFT",
        actionGroupName="SigmaPlatformTools",
        actionGroupExecutor={"lambda": dispatcher_arn},
        functionSchema={"functions": build_functions(tool_names)},
        actionGroupState="ENABLED",
    )

    # Prepare
    bedrock.prepare_agent(agentId=agent_id)
    wait_for_agent(bedrock, agent_id, "PREPARED")
    log("  Prepared.")

    # Alias
    a = bedrock.create_agent_alias(agentId=agent_id, agentAliasName="v1")
    alias_id  = a["agentAlias"]["agentAliasId"]
    alias_arn = a["agentAlias"]["agentAliasArn"]
    log(f"  Alias: {alias_id}")

    return agent_id, alias_id, alias_arn


# ── Step 9: Supervisor ──────────────────────────────────────────────────────────

def get_or_create_supervisor(bedrock, sub_agent_data, dispatcher_arn, guardrail_id, account_id):
    instructions = (AGENTS_DIR / INSTRUCTION_FILES["SupervisorAgent"]).read_text()

    supervisor_id = find_agent_by_name(bedrock, "SupervisorAgent")
    if not supervisor_id:
        r = bedrock.create_agent(
            agentName="SupervisorAgent",
            foundationModel=MODEL_ID,
            instruction=instructions,
            description="Sigma Intelligence Platform — Supervisor",
            idleSessionTTLInSeconds=1800,
            guardrailConfiguration={"guardrailIdentifier": guardrail_id, "guardrailVersion": "DRAFT"},
        )
        supervisor_id = r["agent"]["agentId"]
        log(f"  Agent ID: {supervisor_id}")
        time.sleep(3)

        bedrock.create_agent_action_group(
            agentId=supervisor_id,
            agentVersion="DRAFT",
            actionGroupName="SigmaPlatformTools",
            actionGroupExecutor={"lambda": dispatcher_arn},
            functionSchema={"functions": build_functions(AGENT_TOOLS["SupervisorAgent"])},
            actionGroupState="ENABLED",
        )
    else:
        log(f"  Already exists: {supervisor_id}")

    # Associate sub-agents as collaborators
    log("  Associating sub-agents as collaborators...")
    for name, info in sub_agent_data.items():
        try:
            bedrock.associate_agent_collaborator(
                agentId=supervisor_id,
                agentVersion="DRAFT",
                agentDescriptor={"aliasArn": info["alias_arn"]},
                collaboratorName=name,
                collaborationInstruction=COLLAB_INSTRUCTIONS[name],
                relayConversationHistory="TO_COLLABORATOR",
            )
            log(f"    {name} ✓")
        except bedrock.exceptions.ConflictException:
            log(f"    {name} (already associated)")

    # Prepare supervisor (must re-prepare after adding collaborators)
    log("  Preparing supervisor (includes all collaborators)...")
    bedrock.prepare_agent(agentId=supervisor_id)
    wait_for_agent(bedrock, supervisor_id, "PREPARED")

    # Get latest non-DRAFT version
    versions = bedrock.list_agent_versions(agentId=supervisor_id, maxResults=100)
    non_draft = [
        v for v in versions.get("agentVersionSummaries", [])
        if v["agentVersion"] != "DRAFT"
    ]
    latest_version = str(max(int(v["agentVersion"]) for v in non_draft)) if non_draft else "1"

    # Get or create alias, point to latest version
    alias_id = find_alias(bedrock, supervisor_id, "v1")
    if alias_id:
        bedrock.update_agent_alias(
            agentId=supervisor_id,
            agentAliasId=alias_id,
            agentAliasName="v1",
            routingConfiguration=[{"agentVersion": latest_version}],
        )
        log(f"  Alias updated → version {latest_version}")
    else:
        a = bedrock.create_agent_alias(agentId=supervisor_id, agentAliasName="v1")
        alias_id = a["agentAlias"]["agentAliasId"]
        log(f"  Alias created: {alias_id}")

    return supervisor_id, alias_id


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    log("=" * 60)
    log("SIGMA INTELLIGENCE PLATFORM — BEDROCK SETUP")
    log("Creates: Guardrail, 6 sub-agents, Supervisor agent")
    log("Takes:   5-8 minutes")
    log("Output:  IDs written to lab/.env automatically")
    log("=" * 60)

    env = load_env()
    role_arn = env.get("LAMBDA_ROLE_ARN", "").strip()
    if not role_arn:
        log("\n[ERROR] LAMBDA_ROLE_ARN not set in lab/.env")
        log("Fill it in and re-run this script.")
        sys.exit(1)

    sts        = boto3.client("sts", region_name=REGION)
    account_id = sts.get_caller_identity()["Account"]
    log(f"\nAccount : {account_id}")
    log(f"Region  : {REGION}")

    lc      = boto3.client("lambda",        region_name=REGION)
    bedrock = boto3.client("bedrock-agent", region_name=REGION)

    # 1. Dispatcher Lambda
    dispatcher_arn = deploy_dispatcher(lc, role_arn, account_id)

    # 2. Guardrail
    guardrail_id = get_or_create_guardrail(bedrock)
    update_env({"GUARDRAIL_ID": guardrail_id})

    # 3-8. Sub-agents
    sub_agent_data = {}
    for i, name in enumerate(SUB_AGENTS, 3):
        log(f"\n[{i}/9] Creating {name}...")
        agent_id, alias_id, alias_arn = get_or_create_sub_agent(
            bedrock, name, dispatcher_arn, guardrail_id, account_id
        )
        sub_agent_data[name] = {
            "id": agent_id, "alias_id": alias_id, "alias_arn": alias_arn
        }

    # 9. Supervisor
    log(f"\n[9/9] Creating SupervisorAgent...")
    supervisor_id, supervisor_alias_id = get_or_create_supervisor(
        bedrock, sub_agent_data, dispatcher_arn, guardrail_id, account_id
    )

    # Write all IDs to .env
    update_env({
        "SUPERVISOR_AGENT_ID": supervisor_id,
        "SUPERVISOR_ALIAS_ID": supervisor_alias_id,
        "KNOWLEDGE_BASE_ID":   "LOCAL",
    })

    log("\n" + "=" * 60)
    log("SETUP COMPLETE — all IDs written to lab/.env")
    log("=" * 60)
    log(f"  Supervisor Agent ID : {supervisor_id}")
    log(f"  Supervisor Alias ID : {supervisor_alias_id}")
    log(f"  Guardrail ID        : {guardrail_id}")
    log(f"  Knowledge Base      : LOCAL (no AWS cost)")
    log("")
    log("Continue with Phase 2 manual investigation.")
    log("All agents ready for Phase 3 at 1:30 PM.")
    log("=" * 60)


if __name__ == "__main__":
    main()
