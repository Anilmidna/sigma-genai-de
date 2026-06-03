# Day 13 — The Mystery Domain
## AI for Data Lineage, Governance & Cataloguing

**Wed 3 June 2026 · Final Teaching Day**

---

## The Setup

You have received a dbt project from an unknown company.

No company name. No industry label. No documentation.
Just SQL — and column names.

Your job:
1. Figure out what this company does
2. Govern their data
3. Defend your governance decisions — without a laptop

Anil will assign your team **Mystery A** or **Mystery B**.
Do not look at the other team's folder.

---

## What You Will Learn

- Column-level lineage: how to trace where data came from and what changed
- PII classification: why regex misses half the sensitive columns
- How an LLM reasons about governance for a domain it has never seen
- Where domain expertise beats AI — and where AI beats domain expertise
- Why governance is about defending decisions, not generating documents

---

## Manual-First Exercise — 5 Minutes

**Before opening any script or running any code:**

Open your assigned mystery folder (`lab/mystery_a/` or `lab/mystery_b/`).
Read the SQL files. Do NOT search the internet. Do NOT ask an LLM.

Answer these three questions on paper:
1. What industry is this company in?
2. Name the 3 columns you would encrypt first. Why?
3. Which table would a hacker target? What could they do with it?

Write your answers down. You will compare them to the agent's output.

---

## Prerequisites

```bash
cd repo/day13
pip install -r lab/requirements.txt
aws sts get-caller-identity   # confirm credentials work
```

---

## Steps

### Step 1 — Run the agent on your mystery folder (Lab 1)

Anil will tell you which mystery you have: A or B.

```bash
# If you have Mystery A:
python lab/lineage_agent.py --lab 1 --mystery lab/mystery_a/

# If you have Mystery B:
python lab/lineage_agent.py --lab 1 --mystery lab/mystery_b/
```

The agent asks you 3 questions BEFORE it analyses anything.
Answer honestly — saved and compared to the agent's output at the end.

---

### Step 2 — Watch the agent work

The agent runs in 3 phases:

**Phase 1:** Reads ALL SQL files together and guesses the industry.

**Phase 2:** Analyses each table individually — lineage, PII, access controls.

**Phase 3:** Answers the three governance questions using the catalogue it just built.

Total time: 60-90 seconds for 8 tables.

---

### Step 3 — Read the output

```bash
cat lab/agent_outputs/catalogue_mystery_a.json   # or mystery_b
```

Find these three things:

1. `industry_analysis.industry` — what did the agent think this company is?
2. `pii_surface_area` — the full list of every PII column found
3. `three_questions` — the agent's answers to the same 3 questions you answered manually

---

### Step 4 — The Governance Q&A (no laptops)

Anil cold-calls one person per team. No notes. No screen.

**Questions:**
- *"Your agent classified [column X] as HIGH. Why not CRITICAL?"*
- *"A new engineer joins your team. They ask for SELECT access to [table Y]. Grant or deny? Why?"*
- *"Name one column in your warehouse where the agent got the governance wrong. What did it miss?"*

The last question is the most important. Every agent gets something wrong.
The engineer who can find and explain the error is worth more than the agent.

---

### Step 5 — The Reveal

**Halfway through the Q&A, Anil reveals the industries.**

Teams with Mystery A learn that Mystery B teams had a completely different domain.

**Discussion (10 minutes):**
- Did both mysteries have `bank_account_number`? What's different about the risk?
- Which industry had harder governance decisions? Why?
- What would change if this company expanded to Europe?

---

---

## Lab 2 — Your Own Sigma DataTech Project (Client Deliverable)

After Lab 1 is complete, point the same agent at YOUR dbt project from Day 6.

```bash
python lab/lineage_agent.py --lab 2 --models ../day6/sigma_dbt/models/
```

This produces `lab/agent_outputs/catalogue_sigma.json` — the official governance
catalogue for the Sigma DataTech warehouse. This is the client deliverable.

The agent asks 3 questions before running — answer them. Your answers about
your OWN project should be much stronger than your answers about the mystery domain.

**If they are not, that is the lesson.**

---

## Validation

```bash
python tests/validate_day13.py
```

Expected:
```
OK  catalogue_mystery_a.json (or _b) — 8 tables catalogued
OK  mystery_guess.json — manual answers saved
OK  PII columns found — at least 5
OK  three_questions answered
```

---

## Debrief

### What just happened
You governed a data warehouse you had never seen before, for a company you didn't know existed, using nothing but column names and an LLM. The agent produced lineage maps, PII classifications, access control recommendations, and GDPR guidance in under 90 seconds. In a real DE job, this is what a data governance sprint looks like — a new client, unknown schema, 48 hours to produce a governance brief.

### What AI got right
- Industry identification from column names alone — even with abbreviated names like `uan_number` or `otp_verified`
- Sensitivity escalation: correctly flagged `pan_number` and `bank_account_number` as CRITICAL, not just HIGH
- Cross-table reasoning: noticed that `dim_people` hashes the same columns that `stg_workforce` exposes in plain text

### What AI got wrong — needs your review
- Domain-specific regulations: the agent knows GDPR generically but not RBI's specific data localisation rules or DPDP Act (India's new data protection law)
- Abbreviation blindness: `uan_number` (EPFO Universal Account Number) — the agent may classify this as a generic ID rather than a government-issued identifier
- Business context: the agent cannot know that `pip_initiated` (Performance Improvement Plan) is legally sensitive in Indian employment law — a human governance engineer who knows HR law catches this

### The rule to remember
> *"The agent identifies what exists. The domain expert decides what it means. Governance requires both."*

### Where this fits
The capstone options all need governance. Option B (Agentic DE System) has a Lineage Agent as one of the three required agents. The catalogue JSON format you produced today is exactly what that agent should output.

---

## Bonus Challenge — The Governance Policy

Your catalogue JSON now contains everything needed to draft a data governance policy for this mystery company.

Ask an LLM:

> *"Based on this data catalogue JSON, write a one-page data governance policy for this company.
> Include: data classification tiers, access control matrix, retention periods, and breach notification procedure.
> Make it specific to the columns and tables in the catalogue — no generic templates."*

This is real governance work. Senior DEs at Swiggy, Razorpay, and Walmart Labs do this when new data systems are onboarded.
