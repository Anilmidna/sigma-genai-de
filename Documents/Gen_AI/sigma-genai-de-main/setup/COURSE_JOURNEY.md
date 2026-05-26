# Sigma Intelligence Platform — Your 8-Day Journey
**GenAI for Data Engineering · Sigmoid Bangalore · Days 6–13**

---

## What You Are About to Build

You spent 25 days learning the AWS/Azure data engineering stack with Databricks, Airflow, Snowflake — you know how to move data and transform it at scale. You also completed one week of Gen AI Foundations. 

Now the question changes.

**What if AI could write your pipelines? Review your SQL? Catch bad data before the business does? Fix a 3 AM failure before you wake up?**

Over the next 8 days you will build the **Sigma Intelligence Platform** — one layer per day, every layer connecting to the next. By Day 13 you will have a working, testable, demo-ready intelligent data platform that you built yourself.

Not a tutorial you followed. Not a template you filled in. Something you understand end to end — because you built it line by line.

---

## The Big Shift

The first 25 days: **you operated the tools.**

These 8 days: **you build systems that operate themselves.**

Here is how the thinking changes:

```
Before → You write SQL. You build pipelines. You catch bugs. You write tests.
After  → AI writes SQL. You review it. AI builds scaffolds. You validate them.
         AI catches bugs. You decide if it's right. AI runs at 2 AM. You read the report.
```

The engineer who can direct AI and validate its output is 10x more productive than the engineer who writes everything by hand. That is the skill this bootcamp is designed to give you.

---

## The Platform You Will Build

```
Day 6  →  SQL Brain           "AI reviews SQL like a senior engineer"
  ↓       dbt project + SQL review agent
Day 7  →  Pipeline Brain      "Spec-to-ship in 45 minutes"
  ↓       PySpark + Airflow DAG (AI-generated from your spec)
Day 8  →  DevOps Brain        "AI writes the tests you never had time to write"
  ↓       pytest suite + CI/CD pipeline + auto-generated docs
Day 9  →  Quality Brain       "Catch silent failures before the business does"
  ↓       Great Expectations suite + log RAG chatbot
Day 10 →  Agent Core          "Stop calling AI. Start building AI workers."  ← THE PIVOT
  ↓       ReAct agent + LangGraph agent
Day 11 →  Governance Agent    "The agent that runs your data intake desk at 2 AM"
  ↓       Ingestion + PII detection + lineage extraction
Day 12 →  Self-Heal Agent     "The platform that fixes itself and answers in plain English"
  ↓       Self-heal agent + natural language analytics interface
Day 13 →  Integration Sprint  "Ship it. Defend it."
          Everything wired together → architecture presentation → capstone brief
```

Days 6–9: **you use AI as a tool.** Day 10 is the turning point. Days 11–13: **AI acts autonomously — you are the architect.**

---

## How Each Day Works

Every day follows the same rhythm:

```
15 min  — Recap: yesterday's platform layer → today's connection
30 min  — Concepts: the idea, the why, the production reality
5 min   — Daily Challenge: fast team activity to sharpen the concept
3 hrs   — Core Lab: 4 steps, self-paced, real output by end of session
15 min  — Prod Reality Check: one hard enterprise question, team discussion
30 min  — Stretch Goal: go deeper if you finish early
15 min  — Wrap: leaderboard, tomorrow's hook
```

Every lab ends with a **Debrief** — what AI got right, what AI got wrong, and the one rule to remember. This is not optional reading. This is where the learning consolidates.

---

## The Lab Approach — Manual First, Then AI

Every module follows the same pattern:

1. **You attempt it first** — 2–3 minutes, by hand, no tools
2. **Then you run the script** — AI does the same task
3. **You compare** — what did AI catch that you missed? What did you catch that AI got wrong?

This contrast is the lesson. Blind execution teaches nothing. The manual attempt creates the moment where AI's value becomes real — and its limitations become visible.

---

## How GitHub Works

This is not a read-only course. You ship code every day.

**The flow:**

```
1. Fork this repo once (setup/SETUP_GUIDE.md → Step 1)
2. Each morning: git pull upstream main  ← gets that day's new code from the trainer
3. Run the lab scripts (they generate output files)
4. Validate: python tests/validate_dayX.py  ← confirms you ran everything correctly
5. Push to YOUR fork: git add . && git commit -m "Day X done" && git push
```

Your fork is your portfolio. By Day 13 it contains 8 days of working GenAI code — a real GitHub portfolio you built yourself.

**Why this approach:**
- You get the exact same code as every other student — clean, tested, complete
- Your output files prove you ran it (not just downloaded it)
- Your git history shows your progression day by day

---

## How You Are Assessed Each Day

**During the lab — AhaSlides Flash Quiz**

After each script, a 10-second flash quiz appears on screen. 3 questions per script, directly from the code you just read and ran. You need to have actually read the code to answer in 10 seconds — no time to look it up.

This is not a test of memory. It is a test of whether you understood what you just ran.

**End of day — Validator**

```bash
python tests/validate_dayX.py
```

Green across the board = your work is done. Push and you're done for the day.

**Leaderboard — Team Stars**

You are in a team of 4. Stars are earned daily:
- Complete lab on time = 1 star
- Stretch goal done = 1 bonus star
- Win the daily 5-min challenge = 1 star
- Best Prod Reality Check answer (peer vote) = 1 star

Top team at Day 13 gets first pick of capstone option + recognition on Demo Day.

---

## The Capstone (Day 14–15)

On Day 13 afternoon, capstone options are revealed and assigned. Everything you built in Days 6–13 maps directly to your capstone:

| Option | What You Build | Key Days |
|---|---|---|
| **A — PDF Compliance Bot** | Parse PDFs → check violations → generate compliance report | 8, 10, 11 |
| **B — Agentic DE System** | 3 agents: Quality, Lineage, Pipeline Fixer | 6, 9, 10, 11, 12 |
| **C — RAG-Powered DE Assistant** | Conversational assistant over your data platform | 7, 9, 10, 12 |

You are not starting from scratch on Day 14. You are assembling what you already built.

---

## What This Demands From You

- **Read the code before you run it.** Every script has a mission briefing at the top. Read it. Understand what it does and why before executing.
- **Don't just run and move on.** The debrief at the end of each lab is where the insight lives. Take 5 minutes with it.
- **Engage with the manual-first exercises.** The 2–3 minutes you spend attempting something by hand before the AI does it are the most valuable minutes of each session.
- **Push every day.** Your git history is your work record. A day with no push is a day that didn't happen.

---

## The Tools

| Purpose | Tool |
|---|---|
| LLM — standard tasks | AWS Bedrock Nova Lite (`amazon.nova-lite-v1:0`) |
| LLM — heavy reasoning / agents | AWS Bedrock Nova Pro (`amazon.nova-pro-v1:0`) |
| Agent framework (Day 10+) | LangGraph |
| Data modelling | dbt Core |
| Data quality | Great Expectations |
| Testing | pytest |
| CI/CD | GitHub Actions |
| Warehouse (Day 12) | Snowflake |
| Editor | VS Code |
| Fallback LLM (if Bedrock unavailable) | Ollama qwen2.5:7b |

---

## One Last Thing

Every senior data engineer you will work with has two tools in front of them at any given moment: their IDE and an AI assistant. The engineers who ship are not the ones who resist AI or blindly trust it — they are the ones who direct it precisely and review its output rigorously.

That is what these 8 days train.

**The platform you build here is yours. Ship it.**

---

*Days 6–13 · 26 May – 4 Jun 2026 · Sigma DataTech — building the intelligence layer, one day at a time.*
