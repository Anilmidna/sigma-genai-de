"""
Preflight Check — Run this to verify your environment is ready.
Usage: python setup/preflight.py
"""

import sys

print("=" * 50)
print("SIGMA INTELLIGENCE PLATFORM — PREFLIGHT CHECK")
print("=" * 50)

# Check 1: Python version
print(f"\n[1/5] Python version: {sys.version.split()[0]}", end=" ")
if sys.version_info >= (3, 10):
    print("OK")
else:
    print("FAIL — need 3.10+")

# Check 2: boto3
try:
    import boto3
    print(f"[2/5] boto3: {boto3.__version__} OK")
except ImportError:
    print("[2/5] boto3: MISSING — run: pip install boto3")

# Check 3: Bedrock access
try:
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    response = client.converse(
        modelId="amazon.nova-lite-v1:0",
        messages=[{"role": "user", "content": [{"text": "Reply: OK"}]}],
        inferenceConfig={"maxTokens": 10},
    )
    text = response["output"]["message"]["content"][0]["text"]
    print(f"[3/5] Bedrock Nova Lite: OK (response: '{text}')")
except Exception as e:
    print(f"[3/5] Bedrock Nova Lite: FAIL — {e}")
    print("      Fallback: use Ollama (ollama serve + qwen2.5:7b)")

# Check 4: Ollama
try:
    import requests
    r = requests.get("http://localhost:11434/api/tags", timeout=3)
    models = [m["name"] for m in r.json().get("models", [])]
    if models:
        print(f"[4/5] Ollama: OK (models: {', '.join(models[:3])})")
    else:
        print("[4/5] Ollama: running but no models — run: ollama pull qwen2.5:7b")
except Exception:
    print("[4/5] Ollama: not running (optional fallback — start with: ollama serve)")

# Check 5: Snowflake connector
try:
    import snowflake.connector
    print(f"[5/5] snowflake-connector: OK")
except ImportError:
    print("[5/5] snowflake-connector: MISSING — run: pip install snowflake-connector-python")

print("\n" + "=" * 50)
print("If checks 1-3 pass, you're ready for Day 6.")
print("=" * 50)
