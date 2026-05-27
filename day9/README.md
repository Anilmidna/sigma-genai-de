# Day 9 — Sigma AI Ops Platform
## Case Study: Build One Module of a Real AI Platform

**Duration:** 3–4 hours build + 15-min pitch per team  
**Stack:** AWS Bedrock (Nova Lite/Pro) + DuckDB + Streamlit  
**Data:** Sigma DataTech transaction dataset (same company, new problems)

---

## The Brief

Sigma DataTech is building an AI Ops Platform — a command center that uses AI to run their data operations. Each team builds **one module**. Together, all 9 modules form the complete product.

Your module must survive a 15-minute live demo. It must show where AI helped, where AI was wrong, and what your team decided.

---

## Team Assignments

| Team | Module | Folder |
|------|--------|--------|
| 1 | Fraud Hunter | `team1_fraud_hunter/` |
| 2 | Data Therapist | `team2_data_therapist/` |
| 3 | Pipeline Lawyer | `team3_pipeline_lawyer/` |
| 4 | CFO Challenger | `team4_cfo_challenger/` |
| 5 | Test Saboteur | `team5_test_saboteur/` |
| 6 | Incident Commander | `team6_incident_commander/` |
| 7 | Schema Archaeologist | `team7_schema_archaeologist/` |
| 8 | Synthetic Data Judge | `team8_synthetic_data_judge/` |
| 9 | Runbook Guardian | `team9_runbook_guardian/` |

---

## Setup (do this first, everyone)

```bash
cd repo/day9
pip install -r shared/requirements.txt
python shared/setup_duckdb.py     # creates shared/sigma_platform.duckdb
```

## Run Your Module

```bash
cd repo/day9/team<N>_<name>
streamlit run app.py
```

---

## How Your App Works

Every module has the same 3-round structure:

| Round | What happens |
|-------|-------------|
| **Round 1** | Nova Pro analyses the problem — gives an answer |
| **Round 2** | Nova Lite challenges Round 1 — argues against it |
| **Round 3** | You investigate with DuckDB — make the final call |

The app skeleton is built. **Your job:**
1. Write the Bedrock prompts (the `TODO` sections in `app.py`)
2. Write the DuckDB queries
3. Find the trap in your dataset
4. Save your verdict to `verdict.json`

---

## The Trap

Every module has a pre-seeded problem that breaks a naive solution. You will hit it during development. When you do — that's the moment that matters. Dig in. That's your best pitch material.

---

## 15-Minute Pitch Structure

| Minute | Content |
|--------|---------|
| 0–2 | Business problem your module solves |
| 2–8 | Live demo: Round 1 → Round 2 → Round 3 |
| 8–11 | The trap you found and how you cracked it |
| 11–13 | "What AI Got Wrong" — one specific failure with proof |
| 13–15 | Q&A |

---

## Submission

1. Push your `verdict.json` + completed `app.py` to your fork
2. Share your GitHub link in the class channel
3. One team member demos live — all members answer questions

```bash
git add day9/team<N>_<name>/
git commit -m "Day 9 case study — <module name>"
git push
```

---

## Scoring Criteria (Anil reviews GitHub + live pitch)

| Criteria | What Anil looks for |
|----------|---------------------|
| **Working app** | All 3 rounds run without errors |
| **Trap found** | `verdict.json` shows you discovered and understood the trap |
| **AI critique** | "What AI Got Wrong" is specific, not vague |
| **Business thinking** | Your verdict connects to a real business consequence |
| **Pitch** | Can defend choices under Q&A |

Innovation bonus: anything beyond the skeleton (charts, combined modules, extra Bedrock calls, creative UI) is rewarded.
