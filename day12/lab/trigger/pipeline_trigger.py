"""
Pipeline Trigger — run from your laptop.
Invokes the Bedrock Supervisor Agent and streams its reasoning live.

Usage:
  python lab/trigger/pipeline_trigger.py \
    --bucket sigma-datatech-team1 \
    --message "GMV is zero since 2 AM. Pipeline shows healthy. Investigate and fix."

  # Check health of all Lambda tools first:
  python lab/trigger/pipeline_trigger.py --health-check

  # Clean run (after disaster is fixed, to confirm pipeline is healthy):
  python lab/trigger/pipeline_trigger.py --bucket sigma-datatech-team1 --mode clean
"""

import argparse, boto3, json, os, sys, time
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# ── Optional Langfuse observability ───────────────────────────────────────────
# Set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY in .env to enable.
# Sign up free at https://langfuse.com — all agent traces appear in the dashboard.
try:
    from langfuse import Langfuse as _Langfuse
    _lf = _Langfuse() if os.getenv("LANGFUSE_PUBLIC_KEY") else None
except ImportError:
    _lf = None

REGION             = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
SUPERVISOR_ID      = os.getenv("SUPERVISOR_AGENT_ID", "")
SUPERVISOR_ALIAS   = os.getenv("SUPERVISOR_ALIAS_ID", "TSTALIASID")
DEFAULT_BUCKET     = os.getenv("SIGMA_S3_BUCKET", "")

INCIDENT_MESSAGE   = (
    "Dashboard shows 40,000 transactions today but yesterday showed 1,20,000. "
    "80,000 records are missing. The pipeline shows healthy in all monitors — "
    "Lambda is green, Kinesis is green, Firehose is green, S3 has files. "
    "But Snowflake row count is far below what Kinesis received since 02:00 UTC. "
    "Investigate the root cause, recover the missing records, prevent recurrence. "
    "Write an incident report when done."
)

CLEAN_MESSAGE = (
    "Run a health check on the pipeline. "
    "Confirm data is flowing from Kinesis to Snowflake cleanly. "
    "Report row counts and GMV for the last hour."
)


def health_check():
    lam    = boto3.client("lambda", region_name=REGION)
    tools  = [
        "sigma-tool-check-cloudwatch",
        "sigma-tool-get-kinesis-records",
        "sigma-tool-query-snowflake",
        "sigma-tool-rollback-lambda",
        "sigma-tool-create-alarm",
        "sigma-tool-quarantine-rows",
        "sigma-tool-load-snowflake",
        "sigma-tool-write-report",
        "sigma-tool-send-alert",
        "sigma-mcp-server",
    ]
    print("\nHEALTH CHECK — Lambda Tool Functions")
    print("=" * 50)
    all_ok = True
    for fn in tools:
        try:
            lam.get_function(FunctionName=fn)
            print(f"  OK  {fn}")
        except Exception:
            print(f"  MISSING  {fn}")
            all_ok = False

    print("=" * 50)
    if not SUPERVISOR_ID:
        print("  WARN  SUPERVISOR_AGENT_ID not set in .env")
        all_ok = False
    else:
        print(f"  OK  Supervisor Agent ID: {SUPERVISOR_ID}")

    print(f"\n{'ALL TOOLS READY' if all_ok else 'SOME TOOLS MISSING — run deploy_tools.sh'}")
    return all_ok


def invoke_supervisor(message: str, session_id: str):
    if not SUPERVISOR_ID:
        print("\n[ERROR] SUPERVISOR_AGENT_ID not set in .env")
        print("  Get this from Anil at the start of class.")
        sys.exit(1)

    bedrock = boto3.client("bedrock-agent-runtime", region_name=REGION)

    print("\n" + "=" * 60)
    print("SIGMA INTELLIGENCE PLATFORM — SUPERVISOR AGENT")
    print("=" * 60)
    print(f"  Agent     : {SUPERVISOR_ID}")
    print(f"  Session   : {session_id}")
    print(f"  Triggered : {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    print(f"\nINPUT: {message}\n")
    print("-" * 60)

    start = time.time()

    # Start Langfuse trace for the full supervisor invocation
    lf_trace = _lf.trace(
        name="sigma-supervisor",
        session_id=session_id,
        input={"message": message},
        tags=["bedrock-agent", "day12", "sigma-platform"],
    ) if _lf else None

    try:
        response = bedrock.invoke_agent(
            agentId=SUPERVISOR_ID,
            agentAliasId=SUPERVISOR_ALIAS,
            sessionId=session_id,
            inputText=message,
        )

        # Stream the agent's reasoning and tool calls as they arrive
        for event in response["completion"]:

            # Agent reasoning / text output
            if "chunk" in event:
                text = event["chunk"]["bytes"].decode("utf-8")
                print(text, end="", flush=True)

            # Trace events — show which agents/tools are being called
            elif "trace" in event:
                trace = event["trace"].get("trace", {})

                # Orchestration trace — reasoning steps
                orch = trace.get("orchestrationTrace", {})
                if "rationale" in orch:
                    rat = orch["rationale"].get("text", "")
                    if rat:
                        ts = datetime.now().strftime("%H:%M:%S")
                        print(f"\n[{ts}] SUPERVISOR REASONING: {rat[:120]}...")

                # Tool invocation
                inv = orch.get("invocationInput", {})
                if "actionGroupInvocationInput" in inv:
                    ag  = inv["actionGroupInvocationInput"]
                    fn  = ag.get("function", "?")
                    ts  = datetime.now().strftime("%H:%M:%S")
                    print(f"[{ts}] TOOL CALLED: {fn}")
                    if lf_trace:
                        lf_trace.event(name="tool-called",
                                       input={"tool": fn, "timestamp": ts})

                # Tool result
                obs = orch.get("observation", {})
                if "actionGroupInvocationOutput" in obs:
                    out = obs["actionGroupInvocationOutput"].get("text", "")
                    if out:
                        ts  = datetime.now().strftime("%H:%M:%S")
                        try:
                            parsed = json.loads(out)
                            # Print the most relevant field
                            for key in ["status", "root_cause_hypothesis",
                                        "gmv_gap_inr", "rows_loaded", "alarm_name"]:
                                if key in parsed:
                                    print(f"[{ts}] RESULT: {key} = {parsed[key]}")
                                    break
                        except Exception:
                            print(f"[{ts}] RESULT: {out[:100]}")

                # Sub-agent delegation
                if "agentCollaboratorInvocationInput" in inv:
                    collab      = inv["agentCollaboratorInvocationInput"]
                    ts          = datetime.now().strftime("%H:%M:%S")
                    agent_name  = collab.get("agentCollaboratorName", "?")
                    agent_input = collab.get("input", {}).get("text", "")
                    print(f"[{ts}] DELEGATING TO: {agent_name} "
                          f"— {agent_input[:80]}")
                    if lf_trace:
                        lf_trace.event(name="agent-delegated",
                                       input={"agent": agent_name,
                                              "message": agent_input[:200],
                                              "timestamp": ts})

    except Exception as e:
        print(f"\n[ERROR] Agent invocation failed: {e}")
        print("\nChecks:")
        print("  1. SUPERVISOR_AGENT_ID in .env is correct")
        print("  2. Bedrock agent is in PREPARED state")
        print(f"  3. aws bedrock-agent get-agent --agent-id {SUPERVISOR_ID} --region {REGION}")
        sys.exit(1)

    elapsed = round(time.time() - start, 1)

    # Finalise Langfuse trace
    if lf_trace:
        lf_trace.update(output={"duration_seconds": elapsed, "status": "complete"})
        _lf.flush()

    print("\n" + "=" * 60)
    print(f"  AGENT COMPLETE | Duration: {elapsed}s")
    print("=" * 60)
    print(f"\n  Reports in S3: aws s3 ls s3://{DEFAULT_BUCKET}/reports/ --recursive")
    print(f"  Alarms:        aws cloudwatch describe-alarms --alarm-name-prefix sigma-")
    if _lf and lf_trace:
        print(f"  Langfuse trace: https://cloud.langfuse.com/trace/{lf_trace.id}")


def main():
    parser = argparse.ArgumentParser(description="Sigma Platform Pipeline Trigger")
    parser.add_argument("--bucket",       default=DEFAULT_BUCKET)
    parser.add_argument("--message",      default=INCIDENT_MESSAGE)
    parser.add_argument("--mode",         choices=["incident", "clean"],
                        default="incident")
    parser.add_argument("--health-check", action="store_true")
    args = parser.parse_args()

    if args.health_check:
        health_check()
        return

    if args.mode == "clean":
        msg = CLEAN_MESSAGE
    elif args.message != INCIDENT_MESSAGE:
        msg = args.message
    else:
        msg = INCIDENT_MESSAGE

    session_id = f"sigma-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    invoke_supervisor(msg, session_id)


if __name__ == "__main__":
    main()
