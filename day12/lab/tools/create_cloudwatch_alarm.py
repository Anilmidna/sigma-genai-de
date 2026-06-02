"""
Lambda Tool: create_cloudwatch_alarm
Called by: Hardening Agent
Action group: DataPlatformTools

Creates a CloudWatch metric alarm via boto3.
The alarm goes live in the AWS account immediately after this tool runs.
This is not a recommendation — it is an action.
The Hardening Agent calls this 3 times to create 3 different alarms.
"""

import boto3, json, os
from datetime import datetime, timezone


# Alarm templates the Hardening Agent can choose from.
# Each template maps to a real, sensible alarm for this pipeline.
ALARM_TEMPLATES = {
    "zero_snowflake_load": {
        "AlarmName":          "sigma-snowflake-zero-load",
        "AlarmDescription":   "Fires if Snowflake COPY INTO loaded 0 rows for 2 consecutive 5-min periods. Silent failure indicator.",
        "Namespace":          "SigmaPlatform/Pipeline",
        "MetricName":         "SnowflakeRowsLoaded",
        "Dimensions":         [{"Name": "Table", "Value": "SILVER.TRANSACTIONS"}],
        "Period":             300,
        "EvaluationPeriods":  2,
        "Threshold":          1,
        "ComparisonOperator": "LessThanThreshold",
        "Statistic":          "Sum",
        "TreatMissingData":   "breaching",
    },
    "lambda_version_change": {
        "AlarmName":          "sigma-lambda-version-change",
        "AlarmDescription":   "Fires when Lambda alias LIVE points to a version not in the approved list. Catch bad deploys immediately.",
        "Namespace":          "AWS/Lambda",
        "MetricName":         "Errors",
        "Dimensions":         [{"Name": "FunctionName", "Value": "sigma-kinesis-producer"}],
        "Period":             60,
        "EvaluationPeriods":  1,
        "Threshold":          5,
        "ComparisonOperator": "GreaterThanThreshold",
        "Statistic":          "Sum",
        "TreatMissingData":   "notBreaching",
    },
    "pipeline_row_divergence": {
        "AlarmName":          "sigma-pipeline-row-divergence",
        "AlarmDescription":   "Fires if Kinesis records sent vs Snowflake rows loaded diverges by more than 5% over 10 minutes.",
        "Namespace":          "SigmaPlatform/Pipeline",
        "MetricName":         "RowDivergencePct",
        "Dimensions":         [{"Name": "Pipeline", "Value": "sigma-transactions"}],
        "Period":             600,
        "EvaluationPeriods":  1,
        "Threshold":          5.0,
        "ComparisonOperator": "GreaterThanThreshold",
        "Statistic":          "Maximum",
        "TreatMissingData":   "notBreaching",
    },
}


def lambda_handler(event, context):
    params = {p["name"]: p["value"] for p in event.get("parameters", [])}

    alarm_type = params.get("alarm_type")          # key in ALARM_TEMPLATES
    alarm_name = params.get("alarm_name")          # override name if needed
    description = params.get("description", "")
    sns_topic   = params.get("sns_topic_arn",
                             os.getenv("SNS_TOPIC_ARN", ""))
    region      = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    result = create_alarm(alarm_type, alarm_name, description, sns_topic, region)

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


def create_alarm(alarm_type: str, alarm_name_override: str,
                 description_override: str, sns_topic_arn: str, region: str) -> dict:
    cw = boto3.client("cloudwatch", region_name=region)

    # Build alarm config from template or custom
    if alarm_type and alarm_type in ALARM_TEMPLATES:
        config = dict(ALARM_TEMPLATES[alarm_type])
    else:
        return {"error": f"Unknown alarm_type '{alarm_type}'. "
                         f"Available: {list(ALARM_TEMPLATES.keys())}"}

    if alarm_name_override:
        config["AlarmName"] = alarm_name_override
    if description_override:
        config["AlarmDescription"] = description_override
    if sns_topic_arn:
        config["AlarmActions"]            = [sns_topic_arn]
        config["OKActions"]               = [sns_topic_arn]
        config["InsufficientDataActions"] = []

    try:
        cw.put_metric_alarm(**config)

        # Confirm it exists
        check = cw.describe_alarms(AlarmNames=[config["AlarmName"]])
        alarms = check.get("MetricAlarms", [])
        created = alarms[0] if alarms else {}

        return {
            "status":       "CREATED",
            "alarm_name":   config["AlarmName"],
            "alarm_arn":    created.get("AlarmArn", ""),
            "alarm_state":  created.get("StateValue", "INSUFFICIENT_DATA"),
            "description":  config["AlarmDescription"],
            "threshold":    f"{config['ComparisonOperator']} {config['Threshold']}",
            "sns_topic":    sns_topic_arn,
            "created_at":   datetime.now(timezone.utc).isoformat(),
            "note":         "This alarm is now live in your AWS account.",
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e), "alarm_type": alarm_type}


# ── Local test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    region    = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    sns_topic = os.getenv("SNS_TOPIC_ARN", "")

    print("\nAvailable alarm templates:")
    for key, tmpl in ALARM_TEMPLATES.items():
        print(f"  {key:35} → {tmpl['AlarmDescription'][:60]}...")

    if "--create" in sys.argv:
        alarm_type = sys.argv[sys.argv.index("--create") + 1]
        print(f"\nCreating alarm: {alarm_type}")
        result = create_alarm(alarm_type, None, None, sns_topic, region)
        print(json.dumps(result, indent=2))

    if "--test" in sys.argv:
        assert len(ALARM_TEMPLATES) == 3
        print("\ncreate_cloudwatch_alarm.py test PASSED")
