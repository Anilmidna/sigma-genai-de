import boto3

bedrock = boto3.client("bedrock-agent", region_name="us-east-1")

agent_names = [
    "ForensicsAgent", "ImpactAgent", "RecoveryAgent",
    "RollbackAgent",  "HardeningAgent", "IncidentReportAgent",
    "SupervisorAgent"
]

print("Listing all agents...")
resp = bedrock.list_agents(maxResults=100)
agents_to_delete = []
for a in resp.get("agentSummaries", []):
    if a["agentName"] in agent_names:
        agents_to_delete.append((a["agentName"], a["agentId"]))

if not agents_to_delete:
    print("No matching agents found to delete.")
else:
    for name, agent_id in agents_to_delete:
        print(f"Deleting agent {name} (ID: {agent_id})...")
        try:
            try:
                aliases = bedrock.list_agent_aliases(agentId=agent_id, maxResults=100)
                for alias in aliases.get("agentAliasSummaries", []):
                    alias_id = alias['agentAliasId']
                    if alias_id != "TSTALIASID":
                        print(f"  Deleting alias {alias['agentAliasName']} (ID: {alias_id})...")
                        try:
                            bedrock.delete_agent_alias(agentId=agent_id, agentAliasId=alias_id)
                        except Exception as e:
                            print(f"    Error deleting alias {alias_id}: {e}")
            except Exception as e:
                print(f"  Error listing aliases: {e}")
            
            # Delete the agent
            bedrock.delete_agent(agentId=agent_id, skipResourceInUseCheck=True)
            print(f"  Successfully deleted {name}.")
        except Exception as e:
            print(f"  Error deleting {name}: {e}")

print("Clean up complete!")
