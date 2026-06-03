import os, sys, time, boto3, json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
SUPERVISOR_ID = os.getenv("SUPERVISOR_AGENT_ID", "")
SUPERVISOR_ALIAS = os.getenv("SUPERVISOR_ALIAS_ID", "TSTALIASID")

INCIDENT_MESSAGE = (
    "Dashboard shows 40,000 transactions today but yesterday showed 1,20,000. "
    "80,000 records are missing. The pipeline shows healthy in all monitors — "
    "Lambda is green, Kinesis is green, Firehose is green, S3 has files. "
    "But Snowflake row count is far below what Kinesis received since 02:00 UTC. "
    "Investigate the root cause, recover the missing records, prevent recurrence. "
    "Write an incident report when done. Act fully autonomously. "
    "Failure start timestamp: 2026-06-04T02:00:00Z, failure end timestamp: 2026-06-04T02:20:00Z, transaction date: 2026-06-04."
)

def run_session():
    from botocore.config import Config
    config = Config(read_timeout=600, connect_timeout=600, retries={"max_attempts": 3})
    bedrock = boto3.client("bedrock-agent-runtime", region_name=REGION, config=config)

    session_id = f"sigma-multi-{int(time.time())}"
    print(f"Starting multi-turn session: {session_id}")

    current_prompt = INCIDENT_MESSAGE
    turn = 1

    while turn <= 6:
        print(f"\n============================================================")
        print(f"TURN {turn}")
        print(f"============================================================")
        print(f"Sending prompt: {current_prompt}")
        print("Waiting for response...")

        try:
            response = bedrock.invoke_agent(
                agentId=SUPERVISOR_ID,
                agentAliasId=SUPERVISOR_ALIAS,
                sessionId=session_id,
                inputText=current_prompt,
            )

            full_text = ""
            for event in response["completion"]:
                if "chunk" in event:
                    text = event["chunk"]["bytes"].decode("utf-8")
                    print(text, end="", flush=True)
                    full_text += text
                elif "trace" in event:
                    trace = event["trace"].get("trace", {})
                    orch = trace.get("orchestrationTrace", {})
                    if "rationale" in orch:
                        rat = orch["rationale"].get("text", "")
                        if rat:
                            print(f"\n[REASONING] {rat[:120]}...")
                    inv = orch.get("invocationInput", {})
                    if "actionGroupInvocationInput" in inv:
                        print(f"[TOOL] Calling: {inv['actionGroupInvocationInput'].get('function', '?')}")
                    if "agentCollaboratorInvocationInput" in inv:
                        collab = inv["agentCollaboratorInvocationInput"]
                        print(f"[COLLAB] Delegating to: {collab.get('agentCollaboratorName', '?')}")

            print("\n")
            
            # Check if incident report is written or we reached a final state
            if "reports/" in full_text or "incident_report" in full_text or "prevention" in full_text.lower():
                print("\nIncident report detected or workflow completed!")
                break

        except Exception as e:
            print(f"\n[ERROR] Invoke failed on turn {turn}: {e}")
            break

        # Setup next prompt
        current_prompt = "Yes, please proceed with the planned delegations and tool calls autonomously to complete investigation and recovery."
        turn += 1
        time.sleep(3)

if __name__ == "__main__":
    run_session()
