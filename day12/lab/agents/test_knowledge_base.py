"""
Test Bedrock Knowledge Base retrieval.
Run this twice — before and after the incident — to see RAG in action.

First run:  knowledge base may be empty or have only the seeded documents.
Second run: the incident report from today's session is indexed.
            The same query returns a specific, historically-informed result.
"""

import argparse, boto3, json, os, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
KB_ID  = os.getenv("KNOWLEDGE_BASE_ID", "")

if not KB_ID or KB_ID.upper() in ("LOCAL", "LOCAL_OLLAMA", ""):
    print("Knowledge Base is running locally (no AWS cost).")
    print("Demonstrating RAG concept with local documents instead.\n")
    import glob
    docs_dir = Path(__file__).parent.parent / "knowledge_base"
    docs     = list(docs_dir.rglob("*.md"))
    query    = sys.argv[sys.argv.index("--query") + 1] if "--query" in sys.argv else "Lambda deployment caused Snowflake schema mismatch"
    print(f"Query: {query}\n")
    for doc in docs:
        content = doc.read_text()
        # Simple keyword match (local RAG substitute)
        keywords = [w.lower() for w in query.split() if len(w) > 4]
        score    = sum(1 for kw in keywords if kw in content.lower())
        if score > 0:
            snippet = content[:300].replace("\n", " ")
            print(f"  [{score} matches] {doc.name}")
            print(f"  {snippet}...\n")
    print("This is what a real Knowledge Base retrieval looks like —")
    print("except Bedrock uses vector embeddings instead of keyword search.")
    print("The Forensics Agent retrieves context like this before calling CloudWatch.")
    sys.exit(0)

parser = argparse.ArgumentParser()
parser.add_argument("--query", default="Lambda deployment caused Snowflake schema mismatch")
args = parser.parse_args()

bedrock_kb = boto3.client("bedrock-agent-runtime", region_name=REGION)

print(f"\nKNOWLEDGE BASE RETRIEVAL TEST")
print("=" * 55)
print(f"Knowledge Base ID : {KB_ID}")
print(f"Query             : {args.query}")
print("=" * 55)

try:
    resp = bedrock_kb.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": args.query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": 3}
        },
    )

    results = resp.get("retrievalResults", [])
    if not results:
        print("\n  No results found.")
        print("  First run: knowledge base has only seeded documents.")
        print("  Run the supervisor agent, then run this again.")
        print("  Second run will retrieve today's incident report.")
    else:
        print(f"\n  Found {len(results)} result(s):\n")
        for i, result in enumerate(results, 1):
            content  = result.get("content", {}).get("text", "")
            location = result.get("location", {}).get("s3Location", {}).get("uri", "?")
            score    = result.get("score", 0)
            print(f"  [{i}] Score: {score:.3f}")
            print(f"       Source: {location}")
            print(f"       Content: {content[:200]}...")
            print()

    print("=" * 55)
    print("\nWhat this demonstrates:")
    print("  Run 1 (before incident): generic documents only")
    print("  Run 2 (after incident): incident report indexed, retrieved here")
    print("  The Forensics Agent sees this context before calling CloudWatch.")
    print("  It already knows what happened. Investigation is 10 sec, not 90.")

except Exception as e:
    print(f"\n[ERROR] {e}")
    print("\nChecks:")
    print("  1. KNOWLEDGE_BASE_ID in .env is correct")
    print("  2. Knowledge base is in ACTIVE state in Bedrock console")
    print("  3. IAM role has bedrock:Retrieve permission")
