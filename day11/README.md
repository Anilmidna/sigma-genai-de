# Day 11 — AI Agents for Intelligent Data Ingestion & Quality

**Date:** Monday 2 June 2026 | **Theme:** Build the entry gate of the Sigma Intelligence Platform

---

## ⚠️ PRE-WORK — Complete TONIGHT (Tuesday evening)

**This must be done BEFORE class on Monday.**

1. Open `lab/manual_first_exercise.csv` — 100 rows of Sigma DataTech transaction data
2. Inspect every row carefully
3. For every row that has a data quality issue — fill in the 3 blank columns:

| Column | What to write |
|---|---|
| `issue_found` | Describe the problem in one sentence |
| `severity` | `H` (High) / `M` (Medium) / `L` (Low) |
| `auto_fixable` | `Yes` or `No` |

4. Save as `lab/manual_first_annotated.csv` (keep the original untouched)
5. Push to your fork:

```bash
git add lab/manual_first_annotated.csv
git commit -m "Day 11 pre-work — manual first exercise"
git push
```

**This is evaluated automatically before class starts.**
Your score and missed issues are used for cold calls at 11:30 AM.
Not submitting = cold called first.

---

## What You Will Build Today

An **Ingestion Quality Agent** that autonomously receives a new CSV, profiles it, generates quality rules via LLM, runs checks, auto-fixes safe issues, quarantines bad rows, detects PII, and logs a compliance report — all without a human in the loop.

---

## Scripts — Run in Order

| # | Script | What It Does | Key Output |
|---|--------|-------------|------------|
| 0 | `python lab/sample_data.py` | Generate test CSVs | `data/transactions_raw.csv`, `data/customers_raw.csv` |
| 1 | `python lab/1_multi_agent_pipeline.py` | Supervisor · Swarm · Sequential patterns | `agent_outputs/supervisor_result.json`, `swarm_result.json`, `pipeline_result.json` |
| 2 | `python lab/2_ingestion_quality_agent.py` | **The main lab** — full 6-step quality agent | `quality_report.json`, `ge_expectations.json`, `clean_output.csv`, `quarantine.csv` |
| 3 | `python lab/3_pii_sensitivity_agent.py` | PII detection + sensitivity classification | `pii_scan_report.json`, `sensitivity_report.json` |
| 4 | `python lab/4_stretch_goal_self_heal_loop.py` | Self-heal loop (stretch goal — has TODO) | `self_heal_incident_report.json` |

---

## Setup

```bash
pip install -r lab/requirements.txt
```

AWS credentials must be configured (`aws configure` or environment variables).  
Bedrock model access: `amazon.nova-lite-v1:0` (Lab 1) and `amazon.nova-pro-v1:0` (Labs 2–4).

---

## Validate Your Work

```bash
python tests/validate_day11.py
```

- ✅ Green = core labs done — push to your fork
- 👑 Crown = stretch goal complete

---

## Stretch Goal (Lab 4)

`4_stretch_goal_self_heal_loop.py` has a `TODO` in the `apply_fix()` function.  
Implement the `cast_column_type` fix action. Test it against the `INC-003` type-mismatch failure.  
This requires you to write original code — not just run the script.

---

## Push When Done

```bash
git add .
git commit -m "Day 11 complete"
git push
```
