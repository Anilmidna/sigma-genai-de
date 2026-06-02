"""
Phase 2 Investigation Tool — CloudWatch
Shows Lambda errors, Firehose failures, and Lambda version changes
for the last 8 hours. Look for the exact timestamp when things changed.
"""

import boto3, os, sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
load_dotenv()

region      = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
fn_name     = os.getenv("PRODUCER_LAMBDA_NAME", "sigma-kinesis-producer")
hours_back  = int(sys.argv[1]) if len(sys.argv) > 1 else 8

cw  = boto3.client("cloudwatch", region_name=region)
lam = boto3.client("lambda", region_name=region)
now = datetime.now(timezone.utc)
start = now - timedelta(hours=hours_back)

print(f"\nCLOUDWATCH INVESTIGATION (last {hours_back} hours)")
print("=" * 65)

# ── Lambda version history ────────────────────────────────────────────────────
print(f"\n  Lambda: {fn_name} — version/alias history")
try:
    alias_name = os.getenv("PRODUCER_LAMBDA_ALIAS", "LIVE")
    alias      = lam.get_alias(FunctionName=fn_name, Name=alias_name)
    print(f"    Current alias LIVE → version {alias['FunctionVersion']}")

    versions = lam.list_versions_by_function(FunctionName=fn_name)["Versions"]
    numbered = sorted(
        [v for v in versions if v["Version"] != "$LATEST"],
        key=lambda x: int(x["Version"]),
    )
    for v in numbered:
        ts = v.get("LastModified", "?")
        print(f"    Version {v['Version']:>3}  modified: {ts}  "
              f"{v.get('Description','')[:40]}")
except Exception as e:
    print(f"    ERROR: {e}")

# ── Lambda errors ─────────────────────────────────────────────────────────────
print(f"\n  Lambda errors per 5-min interval:")
resp = cw.get_metric_statistics(
    Namespace="AWS/Lambda",
    MetricName="Errors",
    Dimensions=[{"Name": "FunctionName", "Value": fn_name}],
    StartTime=start, EndTime=now, Period=300,
    Statistics=["Sum"],
)
errors = sorted(resp["Datapoints"], key=lambda x: x["Timestamp"])
error_found = False
for dp in errors:
    if dp["Sum"] > 0:
        ts = dp["Timestamp"].strftime("%H:%M UTC")
        print(f"    {ts}  {int(dp['Sum'])} errors  ← INVESTIGATE")
        error_found = True
if not error_found:
    print("    None — Lambda reporting no errors")
    print("    NOTE: Lambda can run successfully but produce bad output.")
    print("          No errors here does NOT mean the pipeline is healthy.")

# ── Lambda invocation count ───────────────────────────────────────────────────
print(f"\n  Lambda invocations per hour:")
resp2 = cw.get_metric_statistics(
    Namespace="AWS/Lambda",
    MetricName="Invocations",
    Dimensions=[{"Name": "FunctionName", "Value": fn_name}],
    StartTime=start, EndTime=now, Period=3600,
    Statistics=["Sum"],
)
invocations = sorted(resp2["Datapoints"], key=lambda x: x["Timestamp"])
for dp in invocations:
    ts  = dp["Timestamp"].strftime("%Y-%m-%d %H:%M UTC")
    cnt = int(dp["Sum"])
    print(f"    {ts}  {cnt:>6,} invocations")

# ── Firehose delivery freshness ───────────────────────────────────────────────
stream_name = os.getenv("SIGMA_STREAM", "sigma-transactions")
print(f"\n  Firehose data freshness (seconds) — high = delivery delay:")
resp3 = cw.get_metric_statistics(
    Namespace="AWS/Firehose",
    MetricName="DeliveryToS3.DataFreshness",
    Dimensions=[{"Name": "DeliveryStreamName",
                 "Value": f"{stream_name}-firehose"}],
    StartTime=start, EndTime=now, Period=300,
    Statistics=["Maximum"],
)
freshness = sorted(resp3["Datapoints"], key=lambda x: x["Timestamp"])
for dp in freshness:
    ts  = dp["Timestamp"].strftime("%H:%M UTC")
    val = int(dp["Maximum"])
    flag = "  ← DELAYED" if val > 600 else ""
    print(f"    {ts}  {val:>6} sec{flag}")
if not freshness:
    print("    No Firehose metrics found")

print()
print("  KEY QUESTION: Is there a timestamp where Lambda version changed")
print("  AND Firehose freshness spiked AND Lambda errors appeared?")
print("  That 5-minute window is the root cause.")
print()
