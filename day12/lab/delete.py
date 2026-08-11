import boto3

bedrock = boto3.client("bedrock-agent", region_name="us-east-1")

agents = bedrock.list_agents(maxResults=100)["agentSummaries"]

for a in agents:
    print("\n", a["agentName"], a["agentId"])

    aliases = bedrock.list_agent_aliases(
        agentId=a["agentId"],
        maxResults=100
    )["agentAliasSummaries"]

    for alias in aliases:
        print(
            "  ",
            alias["agentAliasName"],
            alias["agentAliasId"]
        )