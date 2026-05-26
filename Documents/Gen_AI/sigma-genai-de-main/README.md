# Sigma Intelligence Platform — GenAI for Data Engineering

**Sigmoid Bangalore | May–Jun 2026 | DevPro Academy**

---

## What This Is

An 8-day hands-on bootcamp where you build a **production-grade AI-native Data Engineering platform** — one layer per day. By Day 13, you have a complete system with SQL review, pipeline generation, data quality monitoring, and autonomous agents.

## Quick Start

```bash
# 1. Fork this repo (click Fork button on GitHub)
# 2. Clone YOUR fork
git clone https://github.com/YOUR-USERNAME/sigma-genai-de.git
cd sigma-genai-de

# 3. Add trainer's repo as upstream
git remote add upstream https://github.com/devproacademy/sigma-genai-de.git

# 4. Install base dependencies
pip install -r setup/requirements.txt

# 5. Pull latest materials (do this every morning)
git pull upstream main
```

## Daily Workflow

```bash
# Morning (get today's materials)
git pull upstream main
cd dayN/lab/

# During class (code along)
python script_name.py
# or
streamlit run app.py

# End of day (submit your work)
git add .
git commit -m "Day N complete — Your Name"
git push origin main
```

## The Journey

| Day | Module | What You Build |
|-----|--------|---------------|
| **6** | SQL Brain | AI code reviewer + NL2SQL pipeline + dbt scaffolding |
| **7** | Pipeline Brain | PySpark + Airflow DAG from English spec |
| **8** | DevOps Brain | pytest suite + GitHub Actions CI/CD + auto-docs |
| **9** | Quality Brain | Great Expectations + log analysis + RAG chatbot |
| **10** | Agent Core | ReAct agent + LangGraph (THE pivot day) |
| **11** | Governance Agent | Auto-ingest + PII detection + lineage + catalogue |
| **12** | Self-Heal + NL | Self-healing agent + English→SQL interface |
| **13** | Integration | Wire it all together + architecture presentations |
| **14** | Capstone Build | Team project (randomly assigned option) |
| **15** | Demo Day | Live presentations to panel |

## Repo Structure

```
├── setup/              ← One-time environment setup
├── day6/
│   ├── lab/            ← Skeleton code (you fill in during class)
│   ├── solutions/      ← Complete code (released next morning)
│   └── demo/           ← Streamlit demo app (trainer shows)
├── day7/
...
├── day15/
└── capstone/           ← Your team's capstone project (Days 14-15)
```

## Rules

1. **Push every day.** Your commit history = your portfolio proof.
2. **No API keys in code.** Use environment variables or `.env` files (gitignored).
3. **Skeletons have TODOs.** Fill them in during class. Don't copy from solutions.
4. **Solutions release next morning.** If you fall behind, pull and study.
5. **Capstone is YOUR work.** You can look at other forks, but submit your own code.

## Tools Used

| Purpose | Tool |
|---------|------|
| LLM (primary) | AWS Bedrock Nova Lite/Pro |
| Agent framework | LangGraph (Day 10+) |
| Data modelling | dbt Core |
| Data quality | Great Expectations |
| Testing | pytest |
| CI/CD | GitHub Actions |
| Warehouse | Snowflake |
| Fallback LLM | Ollama (qwen2.5:7b) |
| Editor | VS Code |

---

*DevPro Academy | Sigmoid Bangalore | GenAI for Data Engineering 2026*
