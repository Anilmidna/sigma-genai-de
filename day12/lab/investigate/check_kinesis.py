"""
Phase 2 Investigation Tool — Kinesis
Shows records sent per hour for the last 8 hours.
Compare this output to check_snowflake.py to find the gap.
"""

import boto3, os, sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
load_dotenv()

region      = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
stream_name = os.getenv("SIGMA_STREAM", "sigma-transactions")
hours_back  = int(sys.argv[1]) if len(sys.argv) > 1 else 8

cw  = boto3.client("cloudwatch", region_name=region)
now = datetime.now(timezone.utc)
start = now - timedelta(hours=hours_back)

print(f"\nKINESIS — Records sent to '{stream_name}' (last {hours_back} hours)")
print("=" * 65)

# IncomingRecords metric
resp = cw.get_metric_statistics(
    Namespace="AWS/Kinesis",
    MetricName="IncomingRecords",
    Dimensions=[{"Name": "StreamName", "Value": stream_name}],
    StartTime=start, EndTime=now, Period=3600,
    Statistics=["Sum"],
)
points = sorted(resp["Datapoints"], key=lambda x: x["Timestamp"])

if not points:
    print("\n  No Kinesis data found. Stream may be inactive.")
else:
    print(f"\n  {'Hour (UTC)':<25} {'Records Sent':>14}")
    print("  " + "-" * 40)
    total = 0
    for dp in points:
        ts  = dp["Timestamp"].strftime("%Y-%m-%d %H:%M")
        cnt = int(dp["Sum"])
        total += cnt
        flag = "  ← SPIKE" if cnt > 1000 else ("  ← ZERO" if cnt == 0 else "")
        print(f"  {ts:<25} {cnt:>14,}{flag}")
    print("  " + "-" * 40)
    print(f"  {'TOTAL':<25} {total:>14,}")

# Throttles
print(f"\n  Throttled records (WriteProvisionedThroughputExceeded):")
resp2 = cw.get_metric_statistics(
    Namespace="AWS/Kinesis",
    MetricName="WriteProvisionedThroughputExceeded",
    Dimensions=[{"Name": "StreamName", "Value": stream_name}],
    StartTime=start, EndTime=now, Period=3600,
    Statistics=["Sum"],
)
throttles = sorted(resp2["Datapoints"], key=lambda x: x["Timestamp"])
if any(dp["Sum"] > 0 for dp in throttles):
    for dp in throttles:
        if dp["Sum"] > 0:
            ts = dp["Timestamp"].strftime("%Y-%m-%d %H:%M")
            print(f"    {ts}  {int(dp['Sum']):,} throttled records  ← INVESTIGATE")
else:
    print("    None — no throttling detected")

print()
print("  TIP: Compare these hourly counts with check_snowflake.py output.")
print("       The hour where Kinesis has records but Snowflake shows 0 is the failure window.")
print()
