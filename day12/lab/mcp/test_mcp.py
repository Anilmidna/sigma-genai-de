"""
Test MCP tool discovery.
Run this after deploy_tools.sh to confirm all 9 tools are reachable.
"""

import boto3, json, os, sys
from dotenv import load_dotenv
load_dotenv()

region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
lam    = boto3.client("lambda", region_name=region)

MCP_FUNCTION = "sigma-mcp-server"

print("\nMCP SERVER — TOOL DISCOVERY TEST")
print("=" * 50)

# Invoke MCP server Lambda with GET /tools
payload = {
    "requestContext": {"http": {"method": "GET"}},
    "rawPath": "/tools",
}

try:
    resp   = lam.invoke(
        FunctionName=MCP_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode(),
    )
    result = json.loads(resp["Payload"].read())
    body   = json.loads(result.get("body", "{}"))
    tools  = body.get("tools", [])

    print(f"\nQuerying MCP server for available tools...\n")
    print(f"Tools available to agents:")
    for i, tool in enumerate(tools, 1):
        params = list(tool.get("parameters", {}).keys())
        print(f"  [{i}] {tool['name']}")
        print(f"      {tool['description'][:80]}...")
        print(f"      Parameters: {params}\n")

    found = len(tools)
    expected = 9
    status = "PASS" if found == expected else "FAIL"
    print(f"{found}/{expected} tools reachable. MCP server {'healthy' if found == expected else 'INCOMPLETE'}.")
    print("=" * 50)

    if found != expected:
        print(f"\n[WARN] Expected {expected} tools but found {found}.")
        print("  Check deploy/deploy_tools.sh ran successfully.")
        print("  Check that sigma-mcp-server Lambda is deployed.")
        sys.exit(1)

    # Test one tool call via MCP
    print("\nTesting one tool call via MCP (check_cloudwatch_metrics)...")
    call_payload = {
        "requestContext": {"http": {"method": "POST"}},
        "rawPath": "/call/check_cloudwatch_metrics",
        "body": json.dumps({"hours_back": 1}),
    }
    call_resp   = lam.invoke(
        FunctionName=MCP_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(call_payload).encode(),
    )
    call_result = json.loads(call_resp["Payload"].read())
    call_body   = json.loads(call_result.get("body", "{}"))
    if "result" in call_body:
        print("  Tool call via MCP: PASS")
    else:
        print(f"  Tool call via MCP: FAIL — {call_body}")

except Exception as e:
    print(f"\n[ERROR] Could not reach MCP server: {e}")
    print("\nChecks:")
    print("  1. Run deploy/deploy_tools.sh first")
    print("  2. Confirm sigma-mcp-server Lambda exists:")
    print("     aws lambda get-function --function-name sigma-mcp-server")
    sys.exit(1)
