# Day 10 — Agentic AI for Data Engineering

## Overview

Four progressively deeper labs showing how AI agents autonomously query, fix, and validate data pipelines. All labs use the same `sigma_platform.duckdb` database (Sigma DataTech Silver layer) and AWS Bedrock (Nova Pro / Lite).

## Lab Sequence

| Lab | File | Concept | Framework |
|-----|------|---------|-----------|
| 1 | `1_react_agent.py` | ReAct loop from scratch | None (raw Python) |
| 2 | `2_langgraph_sql_agent.py` | SQL generate → review → execute loop | LangGraph |
| 3 | `3_crewai_de_team.py` | 3-agent data quality crew | CrewAI |
| 4★ | `4_stretch_goal_agent_memory.py` | Self-healing pipeline + persistent memory | Custom |

★ = stretch goal for fast finishers

## Quick Start

```bash
# 1. Confirm environment is ready
python tests/validate_day10.py

# 2. Run labs in order
cd lab/
python 1_react_agent.py
python 2_langgraph_sql_agent.py
python 3_crewai_de_team.py
python 4_stretch_goal_agent_memory.py   # stretch goal
```

## Install dependencies

```bash
pip install -r lab/requirements.txt
```

## Outputs

All labs write to `lab/agent_outputs/`:

| File | Lab | Contents |
|------|-----|----------|
| `react_trace.json` | 1 | Full ReAct reasoning trace |
| `react_answer.txt` | 1 | Final agent answer |
| `langgraph_trace.json` | 2 | LangGraph execution log |
| `approved_queries.json` | 2 | SQL queries that passed review |
| `crewai_dq_report.json` | 3 | CrewAI quality report |
| `crewai_fix_queries.sql` | 3 | SQL fix statements |
| `healing_log.json` | 4 | Self-healing attempt history |
| `patched_pipeline.py` | 4 | Fixed pipeline code |

Shared memory DB: `lab/agent_memory.db` (SQLite — persists across runs)

## AWS Setup

Labs use **boto3 default credential chain**. Credentials are resolved in order:
1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. `~/.aws/credentials` profile
3. EC2/ECS instance profile

Region: `us-east-1` (hardcoded — Nova Pro/Lite only available here)

Models used:
- `amazon.nova-pro-v1:0` — Labs 1, 2, 3 (primary agents)
- `amazon.nova-lite-v1:0` — Lab 3 (quality guardian, lower cost)

## Snowflake Swap (Lab 2)

Lab 2 includes a Snowflake executor block. To switch from DuckDB to Snowflake, uncomment the `execute_on_snowflake()` block and set env vars:

```bash
export SNOWFLAKE_ACCOUNT=your_account
export SNOWFLAKE_USER=your_user
export SNOWFLAKE_PASSWORD=your_password
export SNOWFLAKE_DATABASE=SIGMA_SILVER
export SNOWFLAKE_SCHEMA=PUBLIC
```
