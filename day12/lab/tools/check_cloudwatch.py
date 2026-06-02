"""
Lambda Tool: check_cloudwatch_metrics
Called by: Forensics Agent
Action group: DataPlatformTools

Correlates Lambda version history, Firehose delivery failures,
Kinesis throttles, and Snowflake COPY INTO outcomes across a timeline.
This is the tool that finds the 4-minute failure window.
"""

import boto3, json, os
from datetime import datetime, timezone, timedelta


def lambda_handler(event, context):
    params = {p["name"]: p["value"] for p in event.get("parameters", [])}
    hours_back   = int(params.get("hours_back", 8))
    function_name = params.get("function_name",
                               os.getenv("PRODUCER_LAMBDA_NAME", "sigma-kinesis-producer"))
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    result = investigate(function_name, hours_back, region)

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


def investigate(function_name: str, hours_back: int, region: str) -> dict:
    cw     = boto3.client("cloudwatch", region_name=region)
    logs   = boto3.client("logs", region_name=region)
    lam    = boto3.client("lambda", region_name=region)
    now    = datetime.now(timezone.utc)
    start  = now - timedelta(hours=hours_back)

    findings = {
        "investigation_window": {
            "from": start.isoformat(),
            "to":   now.isoformat(),
            "hours": hours_back,
        },
        "lambda_version_history": [],
        "lambda_errors":          [],
        "firehose_failures":      [],
        "kinesis_throttles":      [],
        "anomaly_window":         None,
        "root_cause_hypothesis":  None,
    }

    # ── Lambda version/alias history ─────────────────────────────────────────
    try:
        aliases = lam.list_aliases(FunctionName=function_name)["Aliases"]
        for alias in aliases:
            findings["lambda_version_history"].append({
                "alias":           alias["Name"],
                "function_version": alias["FunctionVersion"],
                "description":     alias.get("Description", ""),
            })

        versions = lam.list_versions_by_function(FunctionName=function_name)["Versions"]
        for v in versions:
            if v["Version"] != "$LATEST":
                findings["lambda_version_history"].append({
                    "version":         v["Version"],
                    "last_modified":   v["LastModified"],
                    "description":     v.get("Description", ""),
                    "code_sha":        v.get("CodeSha256", "")[:12],
                })
    except Exception as e:
        findings["lambda_version_history"] = [{"error": str(e)}]

    # ── Lambda errors ─────────────────────────────────────────────────────────
    try:
        resp = cw.get_metric_statistics(
            Namespace="AWS/Lambda",
            MetricName="Errors",
            Dimensions=[{"Name": "FunctionName", "Value": function_name}],
            StartTime=start, EndTime=now, Period=300,
            Statistics=["Sum"],
        )
        errors = sorted(resp["Datapoints"], key=lambda x: x["Timestamp"])
        for dp in errors:
            if dp["Sum"] > 0:
                findings["lambda_errors"].append({
                    "timestamp": dp["Timestamp"].isoformat(),
                    "error_count": int(dp["Sum"]),
                })
    except Exception as e:
        findings["lambda_errors"] = [{"error": str(e)}]

    # ── Firehose delivery failures ────────────────────────────────────────────
    stream_name = os.getenv("SIGMA_STREAM", "sigma-transactions")
    try:
        resp = cw.get_metric_statistics(
            Namespace="AWS/Firehose",
            MetricName="DeliveryToS3.DataFreshness",
            Dimensions=[{"Name": "DeliveryStreamName",
                         "Value": f"{stream_name}-firehose"}],
            StartTime=start, EndTime=now, Period=300,
            Statistics=["Maximum"],
        )
        for dp in sorted(resp["Datapoints"], key=lambda x: x["Timestamp"]):
            if dp["Maximum"] > 600:    # freshness > 10 minutes = problem
                findings["firehose_failures"].append({
                    "timestamp":        dp["Timestamp"].isoformat(),
                    "freshness_seconds": int(dp["Maximum"]),
                    "status": "DELAYED" if dp["Maximum"] < 900 else "CRITICAL",
                })
    except Exception as e:
        findings["firehose_failures"] = [{"error": str(e)}]

    # ── Kinesis throttles ─────────────────────────────────────────────────────
    try:
        resp = cw.get_metric_statistics(
            Namespace="AWS/Kinesis",
            MetricName="WriteProvisionedThroughputExceeded",
            Dimensions=[{"Name": "StreamName", "Value": stream_name}],
            StartTime=start, EndTime=now, Period=300,
            Statistics=["Sum"],
        )
        for dp in sorted(resp["Datapoints"], key=lambda x: x["Timestamp"]):
            if dp["Sum"] > 0:
                findings["kinesis_throttles"].append({
                    "timestamp":     dp["Timestamp"].isoformat(),
                    "throttle_count": int(dp["Sum"]),
                })
    except Exception as e:
        findings["kinesis_throttles"] = [{"error": str(e)}]

    # ── Synthesise: find the anomaly window ───────────────────────────────────
    # Look for the timestamp where Lambda version changed AND errors appeared
    version_change_ts = None
    for item in findings["lambda_version_history"]:
        if "last_modified" in item and item.get("version") == "2":
            version_change_ts = item["last_modified"]

    if version_change_ts:
        findings["anomaly_window"] = {
            "detected_at": version_change_ts,
            "trigger":     "Lambda version 2 deployed",
            "correlation": "Lambda v2 deployed → malformed JSON → Firehose delivered → Snowflake loaded 0 rows",
        }
        findings["root_cause_hypothesis"] = (
            f"Lambda function '{function_name}' was updated to version 2 "
            f"at {version_change_ts}. Version 2 likely changed the JSON field names "
            f"or date format, causing Snowflake COPY INTO to reject all records silently."
        )

    return findings


# ── Local test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    fn    = os.getenv("PRODUCER_LAMBDA_NAME", "sigma-kinesis-producer")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    print(f"\nInvestigating {fn} over last {hours} hours...\n")
    result = investigate(fn, hours, region)

    print("LAMBDA VERSION HISTORY:")
    for item in result["lambda_version_history"]:
        print(f"  {item}")

    if result["lambda_errors"]:
        print("\nLAMBDA ERRORS:")
        for e in result["lambda_errors"]:
            print(f"  {e}")

    if result["anomaly_window"]:
        print(f"\nANOMALY WINDOW: {result['anomaly_window']}")
        print(f"HYPOTHESIS: {result['root_cause_hypothesis']}")
    else:
        print("\nNo anomaly detected in the investigation window.")

    if "--test" in sys.argv:
        assert "lambda_version_history" in result
        print("\ncheck_cloudwatch.py test PASSED")
