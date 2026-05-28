# LLM Observability Lab: "The Blind Agent" (OpenTelemetry + Arize Phoenix)

**Scenario:** You are the AI Engineer responsible for a customer support chatbot powered by AWS Bedrock. Users are complaining that the bot is taking too long to respond, and the financial manager reports that your API token costs are spiking. 

Because you don't have visibility inside the LLM calls (what prompts were sent, how many tokens were generated, and what took so long), you are operating blind. 

In this lab, you will use **OpenTelemetry (OTel)** and **Arize Phoenix** to instrument your Bedrock calls, trace the execution steps, diagnose the latency/cost bottlenecks, and output your verification trace.

---

### Step 1: Install Observability SDKs
Open your terminal and run the following command to install the OpenTelemetry instrumentors and the local Arize Phoenix trace collector:

```bash
pip install arize-phoenix openinference-instrumentation-bedrock opentelemetry-sdk opentelemetry-exporter-otlp
```

*   **arize-phoenix:** Launches the local dashboard and stores tracing telemetry in memory.
*   **openinference-instrumentation-bedrock:** The OpenTelemetry hook that automatically intercepts all calls made using the AWS Bedrock client.
*   **opentelemetry-sdk:** Standard framework for managing span lifecycles.

---

### Step 2: Create the Instrumented App
Create a file named `app_with_otel.py` in your `/labs/llm_observability` directory and paste the following code.

```python
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
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 200,
            "temperature": 0.2
        }
    }
    
    import json
    response = bedrock.invoke_model(
        modelId=model_id,
        body=json.dumps(body)
    )
    
    response_body = json.loads(response.get("body").read().decode("utf-8"))
    output_text = response_body.get("results")[0].get("outputText")
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
```

---

### Step 3: Run the Application
Start your application in the background:
```bash
python app_with_otel.py
```
*You should see logs indicating Phoenix is listening on `http://localhost:6006` and the support agent response printed in the console.*

---

### Step 4: Explore OpenTelemetry Spans & Traces
Open your browser and navigate to:
👉 **[http://localhost:6006](http://localhost:6006)**

Take 5 minutes to play detective and look inside the black box:
1.  **Trace List:** Look at the main table. You should see a trace for `bedrock.invoke_model`.
2.  **Latency Investigation:** Look at the latency column. How many seconds did AWS Bedrock take to process your query?
3.  **Token Usage:** Click on the trace name to open the detailed drawer. Scroll down to see **input tokens** and **output tokens**. How many total tokens did this single call consume?
4.  **Raw Payload:** Observe that you can see the exact prompt sent and output text generated inside the spans properties panel.

---

### Step 5: Automated Lab Verification
While keeping the `app_with_otel.py` script running in your first terminal tab, open a **second terminal tab** and run:

1.  Navigate to the lab folder:
    ```bash
    cd repo/day9/labs/llm_observability
    ```
2.  Execute the verification script:
    ```bash
    python verify_observability.py
    ```

### Output File
If successful, the script connects to your local Phoenix server, checks that OpenTelemetry traces have been correctly collected, and outputs the verification status to:
👉 **`../output/llm_observability_success.json`**

Your automated tracker app will pick up this file to award your day-end score!

---

### 🎓 Key Takeaways for Freshers
1.  **What is Instrumentation?** You didn't modify a single line of your actual agent code to add print logs. OpenTelemetry *instrumentation* dynamically wraps the Bedrock SDK, intercepting the data silently.
2.  **Telemetry Standards:** Spans represent individual steps (functions or API calls) and Traces represent the entire journey. This exact OTel format is what developers use to trace high-volume APIs in production.
3.  **Optimization Metrics:** You can now make decisions based on concrete data (latency, cost, token length) rather than guessing why your agent is slow.
