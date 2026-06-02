"""
Lambda Tool: send_sns_alert
Called by: Supervisor Agent, Incident Report Agent
Action group: DataPlatformTools

Publishes an alert to the SNS topic.
In the lab, your email is subscribed — you will receive this on your phone.
In production this would go to PagerDuty or Slack.
"""

import boto3, json, os
from datetime import datetime, timezone


SEVERITY_SUBJECT = {
    "critical": "[CRITICAL] Sigma Platform Alert",
    "high":     "[HIGH] Sigma Platform Alert",
    "medium":   "[MEDIUM] Sigma Platform Alert",
    "info":     "[INFO] Sigma Platform",
}


def lambda_handler(event, context):
    params = {p["name"]: p["value"] for p in event.get("parameters", [])}

    message   = params.get("message", "")
    severity  = params.get("severity", "high").lower()
    topic_arn = params.get("topic_arn", os.getenv("SNS_TOPIC_ARN", ""))
    region    = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    result = send_alert(message, severity, topic_arn, region)

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "function": event.get("function"),
            "functionResponse": {
                "responseBody": {"TEXT": {"body": json.dumps(result, default=str)}}
            },
        },
    }


def send_alert(message: str, severity: str, topic_arn: str, region: str) -> dict:
    if not topic_arn:
        return {"status": "SKIPPED", "reason": "SNS_TOPIC_ARN not configured"}
    if not message:
        return {"status": "ERROR", "reason": "Empty message"}

    sns     = boto3.client("sns", region_name=region)
    subject = SEVERITY_SUBJECT.get(severity, "[ALERT] Sigma Platform")
    ts      = datetime.now(timezone.utc).isoformat()

    full_message = f"""{message}

---
Severity  : {severity.upper()}
Timestamp : {ts}
Source    : Sigma Intelligence Platform — Autonomous Recovery System
"""

    try:
        resp = sns.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=full_message,
        )
        return {
            "status":     "SENT",
            "message_id": resp["MessageId"],
            "severity":   severity,
            "topic_arn":  topic_arn,
            "sent_at":    ts,
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


# ── Local test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    topic  = os.getenv("SNS_TOPIC_ARN", "")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    if not topic:
        print("Set SNS_TOPIC_ARN in .env to test")
    else:
        msg = ("TEST ALERT — Sigma Intelligence Platform lab test.\n"
               "If you receive this, SNS alerting is configured correctly.")
        result = send_alert(msg, "info", topic, region)
        print(json.dumps(result, indent=2))
        if result["status"] == "SENT":
            print("\nCheck your email — alert should arrive in < 30 seconds.")

    if "--test" in sys.argv:
        print("\nsend_sns_alert.py test PASSED")
