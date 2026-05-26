# Environment Setup Guide
**Complete these steps ONCE before Day 6 starts.**

---

## 1. Python (3.10+)

```bash
python --version
# Expected: Python 3.10.x or higher
```

## 2. AWS CLI + Bedrock Access

```bash
# Check AWS credentials
aws sts get-caller-identity
# Expected: JSON with Account ID

# Check Bedrock Nova access
aws bedrock list-foundation-models --region us-east-1 \
  --query "modelSummaries[?contains(modelId,'nova-lite')].[modelId]" \
  --output table
# Expected: amazon.nova-lite-v1:0 in list
```

## 3. Ollama (Fallback — if Bedrock is unavailable)

```bash
# Install: https://ollama.ai/download
ollama serve          # Start the server
ollama pull qwen2.5:7b   # Download the model (4.4 GB)

# Test
ollama run qwen2.5:7b "Reply with: Ollama is working"
```

## 4. Install Python Packages

```bash
pip install -r setup/requirements.txt
```

## 5. VS Code Extensions (Recommended)

- Python (Microsoft)
- Pylance
- GitLens

## 6. Verify Everything Works

```python
# Save as setup/preflight.py and run
import boto3

client = boto3.client('bedrock-runtime', region_name='us-east-1')
response = client.converse(
    modelId='amazon.nova-lite-v1:0',
    messages=[{'role': 'user', 'content': [{'text': 'Reply: Setup complete'}]}]
)
print(response['output']['message']['content'][0]['text'])
# Expected: "Setup complete" or similar
```

```bash
python setup/preflight.py
```

## 7. Snowflake Account

- Free trial: https://signup.snowflake.com (select AWS, US East region)
- Note: Account Identifier, Username, Password
- Data from Day 5 labs should still exist (SIGMA_DE database)

---

**If any step fails, ask in the Trainer immediately. Don't wait.**
