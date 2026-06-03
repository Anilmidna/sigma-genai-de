import os
import boto3
import phoenix as px
from openinference.instrumentation.bedrock import BedrockInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

# ── 1. LAUNCH PHOENIX LOCAL COLLECTOR ──
print("Launching local Phoenix tracing server...")
session = px.launch_app(port=6006)

# ── 2. INITIALIZE OPENTELEMETRY TRACING ──
# Setup OpenTelemetry provider to export spans to our local Phoenix endpoint
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter("http://localhost:6006/v1/traces")))
trace.set_tracer_provider(provider)

# ── 3. AUTOMATICALLY INSTRUMENT BEDROCK CALLS ──
# This hook intercepts boto3 bedrock calls automatically under the hood
BedrockInstrumentor().instrument()

# ── 4. RUN LLM INFERENCE (Your Bedrock Application) ──
def run_support_agent():
    print("\nRunning support agent inquiry...")
    # Initialize the Bedrock Runtime client
    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
    
    # We simulate a customer support query with a detailed system prompt
    prompt = """
    You are a customer support agent. Answer the user query clearly.
    
    Customer Query: 'I was charged $50.00 twice on my credit card for order #1048. I want a refund.'
    """
    
    # Target AWS Bedrock Nova model (or whatever model you are using for Day 9)
    model_id = "amazon.nova-lite-v1:0"
    
    body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "inferenceConfig": {
            "maxTokens": 200,
            "temperature": 0.2
        }
    }
    
    import json
    response = bedrock.invoke_model(
        modelId=model_id,
        body=json.dumps(body)
    )
    
    response_body = json.loads(response.get("body").read().decode("utf-8"))
    output_text = response_body["output"]["message"]["content"][0]["text"]
    print(f"\nResponse from LLM:\n{output_text}")

if __name__ == "__main__":
    # Run the LLM call which will trigger OTel tracing
    run_support_agent()
    
    print("\nKeep this script running so the Phoenix server stays active!")
    print("Press Ctrl+C to exit when you are done.")
    
    # Keep the server alive so you can inspect the dashboard
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down tracing server.")