import boto3
import json

client = boto3.client("bedrock-runtime", region_name="us-east-1")

def test_model(model_id):
    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "inferenceConfig": {"max_new_tokens": 100},
            "messages": [{"role": "user", "content": [{"text": "Say hello in one line"}]}]
        })
    )
    result = json.loads(response["body"].read())
    print(f"{model_id}: {result['output']['message']['content'][0]['text']}")

test_model("amazon.nova-lite-v1:0")
test_model("amazon.nova-pro-v1:0")