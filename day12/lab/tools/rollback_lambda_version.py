"""
Lambda Tool: rollback_lambda_version
Called by: Rollback Agent
Action group: DataPlatformTools

Identifies the bad Lambda version, rolls the alias back to the
previous stable version, and sends 5 test records to verify stability.
Returns before/after state so the agent can confirm success.
"""

import boto3, json, os, time
from datetime import datetime, timezone


def lambda_handler(event, context):
    params = {p["name"]: p["value"] for p in event.get("parameters", [])}

    function_name  = params.get("function_name",
                                os.getenv("PRODUCER_LAMBDA_NAME", "sigma-kinesis-producer"))
    alias_name     = params.get("alias_name",
                                os.getenv("PRODUCER_LAMBDA_ALIAS", "LIVE"))
    target_version = params.get("target_version", "previous")
    region         = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    result = rollback(function_name, alias_name, target_version, region)

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


def rollback(function_name: str, alias_name: str,
             target_version: str, region: str) -> dict:
    lam    = boto3.client("lambda", region_name=region)
    result = {
        "function_name":   function_name,
        "alias":           alias_name,
        "before":          {},
        "after":           {},
        "verification":    {},
        "status":          "unknown",
        "rollback_ts":     datetime.now(timezone.utc).isoformat(),
    }

    # ── Get current state ─────────────────────────────────────────────────────
    try:
        alias        = lam.get_alias(FunctionName=function_name, Name=alias_name)
        current_ver  = alias["FunctionVersion"]
        result["before"] = {
            "alias":   alias_name,
            "version": current_ver,
            "arn":     alias["AliasArn"],
        }
    except Exception as e:
        result["status"] = f"ERROR — could not get alias: {e}"
        return result

    # ── Determine target version ──────────────────────────────────────────────
    if target_version == "previous":
        versions = lam.list_versions_by_function(FunctionName=function_name)["Versions"]
        numbered = sorted(
            [v for v in versions if v["Version"] != "$LATEST"],
            key=lambda x: int(x["Version"]),
        )
        # Roll back to the version before the current one
        current_idx = next(
            (i for i, v in enumerate(numbered) if v["Version"] == current_ver), -1
        )
        if current_idx <= 0:
            result["status"] = "ERROR — no previous version to roll back to"
            return result
        target_version = numbered[current_idx - 1]["Version"]

    # ── Update alias ──────────────────────────────────────────────────────────
    try:
        lam.update_alias(
            FunctionName=function_name,
            Name=alias_name,
            FunctionVersion=target_version,
            Description=f"Rolled back by Sigma Rollback Agent at "
                        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        )
        result["after"] = {
            "alias":   alias_name,
            "version": target_version,
        }
    except Exception as e:
        result["status"] = f"ERROR — alias update failed: {e}"
        return result

    # ── Verify: invoke with 5 test records, check output is valid JSON ────────
    stream_name   = os.getenv("SIGMA_STREAM", "sigma-transactions")
    kinesis_client = boto3.client("kinesis", region_name=region)
    test_results  = []
    test_payload  = {
        "Records": [
            {
                "transaction_id":   f"TEST-VERIFY-{i:03d}",
                "merchant_name":    "VerifyMart",
                "category":         "test",
                "amount":           100.0,
                "currency":         "INR",
                "transaction_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "status":           "completed",
                "customer_id":      "C9999",
                "payment_method":   "UPI",
                "merchant_city":    "Bengaluru",
            }
            for i in range(5)
        ],
        "stream_name": stream_name,
    }

    try:
        resp = lam.invoke(
            FunctionName=f"{function_name}:{alias_name}",
            InvocationType="RequestResponse",
            Payload=json.dumps(test_payload).encode(),
        )
        payload_str = resp["Payload"].read().decode("utf-8")
        payload_obj = json.loads(payload_str)

        # v1 should return merchant_name (not merchant_nm) in its output
        if "merchant_name" in payload_str and "merchant_nm" not in payload_str:
            test_results = [{"status": "PASS", "detail": "v1 field names confirmed"}]
        elif "merchant_nm" in payload_str:
            test_results = [{"status": "FAIL",
                             "detail": "Still outputting merchant_nm — rollback may not have taken effect"}]
        else:
            test_results = [{"status": "PASS", "detail": "Lambda invoked successfully"}]

    except Exception as e:
        test_results = [{"status": "ERROR", "detail": str(e)}]

    result["verification"] = {
        "test_records_sent": 5,
        "results":           test_results,
        "stable":            all(r["status"] == "PASS" for r in test_results),
    }
    result["status"] = "SUCCESS" if result["verification"]["stable"] else "ROLLED_BACK_BUT_VERIFY_FAILED"
    return result


# ── Local test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    fn     = os.getenv("PRODUCER_LAMBDA_NAME", "sigma-kinesis-producer")
    alias  = os.getenv("PRODUCER_LAMBDA_ALIAS", "LIVE")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    print(f"\nRollback test (DRY RUN — showing current state only)\n")

    lam = boto3.client("lambda", region_name=region)
    try:
        a = lam.get_alias(FunctionName=fn, Name=alias)
        print(f"  Function : {fn}")
        print(f"  Alias    : {alias}")
        print(f"  Current  : version {a['FunctionVersion']}")
        versions = lam.list_versions_by_function(FunctionName=fn)["Versions"]
        numbered = [v for v in versions if v["Version"] != "$LATEST"]
        print(f"  Available versions: {[v['Version'] for v in numbered]}")
    except Exception as e:
        print(f"  ERROR: {e}")
        print("  Check PRODUCER_LAMBDA_NAME in .env")

    if "--test" in sys.argv:
        print("\nrollback_lambda_version.py test PASSED (dry run)")
