import json
import os
import sys

def main():
    print("Checking LLM Observability Lab completion status...")
    
    # 1. Check if Phoenix client can connect
    try:
        from phoenix.client import Client
    except ImportError:
        print("❌ Error: arize-phoenix is not installed. Run:")
        print("   pip install arize-phoenix")
        sys.exit(1)
        
    try:
        client = Client(endpoint="http://localhost:6006")
        # Test connection by listing projects
        client.get_projects()
    except Exception as e:
        print("❌ Error: Could not connect to local Phoenix server on http://localhost:6006.")
        print("   Ensure your python script with px.launch_app() is running in the background.")
        sys.exit(1)
        
    print("✓ Phoenix Server Connection: SUCCESS")
    
    # 2. Get Spans Dataframe
    try:
        # Try spans namespace first, fallback to direct client call
        try:
            spans_df = client.spans.get_spans_dataframe()
        except AttributeError:
            spans_df = client.get_spans_dataframe()
    except Exception as e:
        print(f"❌ Error: Failed to fetch spans from Phoenix: {e}")
        sys.exit(1)
        
    if spans_df.empty:
        print("❌ Error: Phoenix is running, but no trace data was found.")
        print("   Make sure you ran your Bedrock LLM script after instrumenting it.")
        sys.exit(1)
        
    total_spans = len(spans_df)
    
    # Check for LLM spans
    llm_spans = 0
    if "span_kind" in spans_df.columns:
        llm_spans = len(spans_df[spans_df["span_kind"] == "LLM"])
        
    print(f"✓ Total Telemetry Spans Captured: {total_spans}")
    print(f"✓ LLM Inference Calls Detected: {llm_spans}")
    
    if total_spans > 0:
        print("🎉 Verification SUCCESS! OpenTelemetry traces successfully captured by local collector.")
        
        # Ensure output directory exists
        output_dir = "../output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        result = {
            "status": "success",
            "phoenix_active": True,
            "total_spans_captured": total_spans,
            "llm_inference_calls": llm_spans,
            "llm_observability_verified": True
        }
        
        output_file = os.path.join(output_dir, "llm_observability_success.json")
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"✓ Created '{output_file}' for the tracker app.")
    else:
        print("❌ Error: No spans captured. Run your Bedrock agent script again.")
        sys.exit(1)

if __name__ == "__main__":
    main()
