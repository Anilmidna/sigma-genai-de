"""
==============================================================================
LANGFUSE MINI LAB — The Blind Agent Problem
==============================================================================
MISSION BRIEF
-------------
Sigma DataTech's quality agent ran last night. This morning, the BI team
calls: "Three merchants show negative GMV in Snowflake. Something quarantined
the wrong rows."

You have no logs. You have no idea which LLM call made the wrong decision.
This is the Black Box Problem — and it happens every week in production.

This script simulates 5 quality-check decisions made by the agent overnight.
One of them is WRONG — a false positive that quarantined a legitimate
₹9.8L hospital transaction.

YOUR JOB:
  1. Run this script
  2. Open https://cloud.langfuse.com → your project → Traces
  3. Find the bad decision (wrong quarantine)
  4. Read the exact prompt that caused it
  5. Fix the prompt in this script
  6. Re-run and verify the decision flips to PASS

Without Langfuse: you would grep through 847 log lines and maybe find it.
With Langfuse: 30 seconds.

SETUP (one-time):
  pip install langfuse boto3 --break-system-packages -q
  export LANGFUSE_PUBLIC_KEY="pk-lf-..."
  export LANGFUSE_SECRET_KEY="sk-lf-..."
  export LANGFUSE_HOST="https://cloud.langfuse.com"

RUN:
  python lab/5_langfuse_trace_demo.py
==============================================================================
"""

import boto3, json, os, time
from datetime import datetime
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

# ── Init ──────────────────────────────────────────────────────────────────────
lf     = Langfuse()
client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
MODEL  = "amazon.nova-lite-v1:0"
RUN_ID = datetime.now().strftime("%H%M%S")

# ── 5 transactions from last night's batch ────────────────────────────────────
TRANSACTIONS = [
    {
        "id": "TXN100441",
        "merchant": "QuickMart",
        "amount": 4521.50,
        "currency": "INR",
        "date": "2026-06-01",
        "note": "Standard retail transaction",
        "expected": "PASS",
    },
    {
        "id": "TXN100467",
        "merchant": "FuelPlus",
        "amount": -892.00,
        "currency": "INR",
        "date": "2026-06-01",
        "note": "Negative amount — refund or error",
        "expected": "QUARANTINE",
    },
    {
        "id": "TXN100489",
        "merchant": "Apollo Hospital",
        "amount": 980000.00,
        "currency": "INR",
        "date": "2026-06-01",
        # ← THIS IS THE BAD PROMPT — it omits merchant context
        # The agent sees only the amount and flags it as outlier
        # Fix: add "merchant_category: healthcare" to the prompt
        "note": "Large hospital invoice — legitimate corporate payment",
        "expected": "PASS",
    },
    {
        "id": "TXN100512",
        "merchant": "CloudStore",
        "amount": 15230.00,
        "currency": "XYZ",
        "date": "2026-06-01",
        "note": "Unknown currency code",
        "expected": "QUARANTINE",
    },
    {
        "id": "TXN100534",
        "merchant": "CafeBlend",
        "amount": 340.00,
        "currency": "INR",
        "date": "2026-12-31",
        "note": "Future date — cannot be a real transaction",
        "expected": "QUARANTINE",
    },
]

# ── Prompt builder — THIS is what you fix ─────────────────────────────────────
def build_prompt(txn: dict) -> str:
    """
    Build the quality-check prompt for a transaction.

    KNOWN BUG: For TXN100489 (Apollo Hospital), the prompt does not include
    merchant_category. The LLM sees ₹9,80,000 with no context and flags it
    as an outlier. Fix: add merchant_category to the prompt for all transactions.
    """
    return f"""You are a data quality agent for Sigma DataTech, a fintech platform.

Evaluate this transaction and return one of: PASS | QUARANTINE | FLAG

Transaction:
  id:       {txn['id']}
  merchant: {txn['merchant']}
  amount:   {txn['amount']} {txn['currency']}
  date:     {txn['date']}

Rules:
  - QUARANTINE if: negative amount, unknown currency, future date, null id
  - FLAG if: amount > 500000 INR with no business context
  - PASS if: all fields valid and amount is reasonable for the merchant type

Respond with JSON only:
{{"decision": "PASS|QUARANTINE|FLAG", "reason": "one sentence", "confidence": 0.0-1.0}}"""


# ── Bedrock call with Langfuse tracing ────────────────────────────────────────
@observe()
def evaluate_transaction(txn: dict) -> dict:
    prompt = build_prompt(txn)

    # Tag this trace so you can filter in Langfuse dashboard
    langfuse_context.update_current_trace(
        name=f"quality-check-{txn['id']}",
        tags=["day11", "quality-agent", f"run-{RUN_ID}"],
        metadata={
            "transaction_id": txn["id"],
            "merchant":       txn["merchant"],
            "amount":         txn["amount"],
            "expected":       txn["expected"],
        },
    )

    start = time.time()

    # Bedrock call
    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 200, "temperature": 0.0},
    }
    resp     = client.invoke_model(modelId=MODEL, body=json.dumps(body))
    raw      = json.loads(resp["body"].read())
    text     = raw["output"]["message"]["content"][0]["text"].strip()
    usage    = raw.get("usage", {})
    latency  = int((time.time() - start) * 1000)

    # Parse LLM response
    try:
        start_i = text.index("{")
        end_i   = text.rindex("}") + 1
        result  = json.loads(text[start_i:end_i])
    except Exception:
        result  = {"decision": "ERROR", "reason": text[:100], "confidence": 0.0}

    decision = result.get("decision", "ERROR")
    correct  = decision == txn["expected"]

    # Log the observation — this is what you see in Langfuse
    langfuse_context.update_current_observation(
        input=prompt,
        output=text,
        usage={
            "input":  usage.get("inputTokens", 0),
            "output": usage.get("outputTokens", 0),
        },
        metadata={
            "latency_ms":  latency,
            "decision":    decision,
            "expected":    txn["expected"],
            "correct":     correct,
            "confidence":  result.get("confidence", 0.0),
        },
    )

    # Score the trace — 1.0 = correct, 0.0 = wrong decision
    # This is what a production eval pipeline does automatically
    lf.score(
        trace_id=langfuse_context.get_current_trace_id(),
        name="decision-correct",
        value=1.0 if correct else 0.0,
        comment=f"Expected {txn['expected']}, got {decision}. {result.get('reason','')}",
    )

    return {
        "id":        txn["id"],
        "merchant":  txn["merchant"],
        "amount":    txn["amount"],
        "decision":  decision,
        "expected":  txn["expected"],
        "correct":   correct,
        "reason":    result.get("reason", ""),
        "latency_ms":latency,
        "tokens":    usage.get("inputTokens", 0) + usage.get("outputTokens", 0),
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print()
    print("=" * 65)
    print("LANGFUSE MINI LAB — Quality Agent Trace Demo")
    print(f"Run ID: {RUN_ID}  |  Model: {MODEL}")
    print("=" * 65)
    print()
    print("Sending 5 transactions to quality agent...")
    print("Open https://cloud.langfuse.com → Traces while this runs.")
    print()

    results = []
    for txn in TRANSACTIONS:
        print(f"  Checking {txn['id']} | {txn['merchant']:<20} | ₹{txn['amount']:>12,.2f}  ...", end=" ", flush=True)
        r = evaluate_transaction(txn)
        results.append(r)
        mark = "✓" if r["correct"] else "✗ WRONG"
        print(f"{r['decision']:<12} {mark}  ({r['latency_ms']}ms, {r['tokens']} tokens)")

    lf.flush()

    # ── Results table ─────────────────────────────────────────────────────────
    print()
    print("=" * 65)
    print("RESULTS")
    print(f"{'TXN':<14} {'Merchant':<22} {'Decision':<12} {'Expected':<12} {'OK?'}")
    print("-" * 65)
    wrong = []
    for r in results:
        mark = "✓" if r["correct"] else "✗"
        print(f"  {r['id']:<12} {r['merchant']:<22} {r['decision']:<12} {r['expected']:<12} {mark}")
        if not r["correct"]:
            wrong.append(r)

    total_tokens  = sum(r["tokens"]  for r in results)
    total_latency = sum(r["latency_ms"] for r in results)

    print()
    print(f"  Total tokens used : {total_tokens}")
    print(f"  Total latency     : {total_latency}ms")
    print(f"  Correct decisions : {len(results) - len(wrong)}/{len(results)}")
    print("=" * 65)

    if wrong:
        print()
        print("⚠  WRONG DECISIONS DETECTED:")
        for r in wrong:
            print(f"   {r['id']} — {r['merchant']}")
            print(f"   Decision: {r['decision']}  |  Expected: {r['expected']}")
            print(f"   Agent said: \"{r['reason']}\"")
            print()
        print("  → Open Langfuse. Find this trace. Read the prompt.")
        print("  → Ask: what information was MISSING that caused this?")
        print("  → Fix build_prompt() and re-run. Verify it flips to PASS.")
    else:
        print()
        print("✓ All decisions correct — you fixed the bad prompt!")

    print()
    print(f"  Traces at: https://cloud.langfuse.com")
    print(f"  Filter by tag: run-{RUN_ID}")
    print("=" * 65)
    print()

    # Save results for validator
    out_dir = os.path.join(os.path.dirname(__file__), "agent_outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "langfuse_demo_results.json")
    with open(out_path, "w") as f:
        json.dump({
            "run_id":   RUN_ID,
            "results":  results,
            "correct":  len(results) - len(wrong),
            "total":    len(results),
            "student_judgment": input(
                "\nOne bad decision slipped through. What would you add to the prompt"
                " to prevent it? (1 sentence): "
            ).strip() or "NOT ANSWERED",
        }, f, indent=2)
    print(f"  Saved: {out_path}")
    print()


if __name__ == "__main__":
    main()
