# Day 10 Labs — Agentic AI for Data Engineering

## Setup (do this first)

```bash
cd repo/day10
python tests/validate_day10.py    # must show all ✅ before starting
pip install -r lab/requirements.txt
```

## Labs — run in order

| Lab | File | What you build |
|-----|------|---------------|
| 1 | `1_react_agent.py` | ReAct loop from scratch — raw Python, no framework |
| 2 | `2_langgraph_sql_agent.py` | LangGraph: SQL generate → review → execute with memory |
| 3 | `3_crewai_de_team.py` | CrewAI: 3-agent data quality crew |
| 4★ | `4_stretch_goal_agent_memory.py` | Self-healing pipeline — catches errors, patches, caches fixes |

```bash
cd lab/
python 1_react_agent.py
python 2_langgraph_sql_agent.py
python 3_crewai_de_team.py
python 4_stretch_goal_agent_memory.py   # stretch goal
```

## Outputs (written to `lab/agent_outputs/`)

| File | Lab |
|------|-----|
| `react_trace.json` | 1 |
| `react_answer.txt` | 1 |
| `langgraph_trace.json` | 2 |
| `approved_queries.json` | 2 |
| `crewai_dq_report.json` | 3 |
| `crewai_fix_queries.sql` | 3 |
| `healing_log.json` | 4 |
| `patched_pipeline.py` | 4 |

Shared memory: `lab/agent_memory.db` — persists across all labs and runs.

## AWS

Region: `us-east-1`. Credentials via `~/.aws/credentials` or env vars.  
Models: `amazon.nova-pro-v1:0` (Labs 1–3), `amazon.nova-lite-v1:0` (Lab 3 Guardian).
