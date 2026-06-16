# 📁 Team 3 — Pipeline Lawyer: Step-by-Step Guide

> This file documents every step taken to build the project. Use it as a reference.

---

## 🧠 What Is This Project?

You are building a **Streamlit web app** called **"Pipeline Lawyer"**.

The story:
- A junior Data Engineer submitted a **Pull Request (PR)** to fix a bug in the Silver data pipeline.
- The fix *looks* correct. Tests pass.
- But the tech lead suspects something is wrong.
- **Your job:** Use two AI models to argue both sides, then judge the PR yourself.

---

## 🏗️ Tech Stack

| Tool | Purpose |
|------|---------|
| **Streamlit** | Web UI framework (Python-based) |
| **AWS Bedrock (Nova Pro)** | Smarter AI — argues FOR the PR |
| **AWS Bedrock (Nova Lite)** | Faster AI — argues AGAINST the PR |
| **DuckDB** | Lightweight SQL database (local file) |
| **Python** | Glue language |

---

## ⚖️ The 3-Round Structure

### Round 1 — AI Prosecutor (PRO-merge)
- Model: **Nova Pro** (smarter, deeper reasoning)
- Reads both pipeline versions (v1 and v2)
- Writes a legal brief arguing **FOR** merging the PR
- Lists every improvement

### Round 2 — AI Defense (AGAINST-merge)
- Model: **Nova Lite** (faster, cheaper)
- Reads the same code
- Writes a legal brief arguing **AGAINST** merging
- Finds risks, edge cases, hidden failures

### Round 3 — Your Verdict
- You (the human judge) decide: **APPROVE / REJECT / REQUEST CHANGES**
- You write ONE sentence explaining your decision
- Result is saved to `verdict.json`

---

## 🪤 The Hidden Trap

The v2 pipeline fix **does** solve the original idempotency bug.
BUT — it introduces a **new bug** that only appears when the function is called **more than once**.

This can be reproduced in **5 lines of Python**.

> Your challenge: Find this bug, reproduce it, and explain it in your pitch.

---

## 📂 Project File Structure

```
day9/
├── shared/
│   ├── bedrock_helper.py      ← Helper to call Nova Lite / Nova Pro
│   ├── requirements.txt       ← Python dependencies
│   ├── setup_duckdb.py        ← Creates the shared database
│   └── sigma_platform.duckdb  ← The database (created after setup)
│
└── team3_pipeline_lawyer/
    ├── brief.md               ← Original problem statement
    ├── starter.py             ← Starting code scaffold
    ├── app.py                 ← ✅ YOUR MAIN FILE (to be built)
    ├── verdict.json           ← ✅ YOUR FINAL VERDICT (to be created)
    └── GUIDE.md               ← This file
```

---

## 🪜 Steps To Build The Project

---

### ✅ STEP 1 — Understand the Project (YOU ARE HERE)
- Read `brief.md` and this `GUIDE.md`
- Understand the 3-round structure
- Know the tech stack

---

### ✅ STEP 2 — Setup & Install Dependencies
```bash
cd /path/to/day9
pip install -r shared/requirements.txt
python shared/setup_duckdb.py
```
**What this does:**
- Installs streamlit, boto3, duckdb, pandas, plotly
- Creates `shared/sigma_platform.duckdb` with seeded data

**Output after running setup_duckdb.py:**
```
bronze_transactions     21 rows
silver_transactions     14 rows
gold_merchant_performance 8 rows
gold_daily_summary       9 rows
pipeline_versions        3 rows  ← v1, v2, stack_trace
```

**🔍 Key Discovery — The Trap (found in sample_data.py):**

The pipeline code is already stored in the DB under `pipeline_versions` table.

- **v1 (buggy):** No deduplication → crashes with `ConstraintException` on duplicate PKs
- **v2 ("fixed"):** Uses `seen_ids = set()` at module-level to skip duplicates
- **The hidden trap in v2:** `seen_ids` is a **module-level global variable**.
  When `load_silver()` is called a **second time in the same Python session**,
  `seen_ids` still holds all IDs from the first run → **0 rows are written silently!**
  The pipeline appears to succeed but does nothing. 🔥

---

### ✅ STEP 3 — Build the Streamlit App (`app.py`)

**File created:** `team3_pipeline_lawyer/app.py`

**How to run:**
```bash
cd day9/team3_pipeline_lawyer
streamlit run app.py
```

**What the app does:**

| Section | Description |
|---------|-------------|
| Hero Banner | Title, badges, team info |
| Case Brief | Shows v1 and v2 code side by side (expandable) |
| Round 1 | Button → calls Nova Pro → shows PRO-MERGE brief |
| Round 2 | Button → calls Nova Lite → shows AGAINST-MERGE brief |
| Side-by-Side | Both briefs shown together (appears after both generated) |
| The Trap | 5-line bug reproduction explained visually |
| DuckDB Proof | SQL query to verify row counts |
| Correct Fix | Option A (move to local scope) + Option B (DB-level) |
| Verdict Form | APPROVE / REJECT / REQUEST CHANGES + reason |
| Save Verdict | Writes to `verdict.json` |
| What AI Got Wrong | Analysis of which model missed the bug |

**Key design decisions:**
- `seen_ids` v2 code is loaded directly from `pipeline_versions` DB table (not hardcoded)
- Both AI prompts are crafted to guide the models toward the global-state bug
- Nova Lite prompt explicitly asks: *"what happens if load_silver() is called more than once?"*
- Verdict is auto-structured and saved to `verdict.json` with full bug details

---

### ⏳ STEP 4 — Build the Streamlit App (`app.py`)
- Round 1: Call **Nova Pro** with v1 + v2 code → get PRO-merge brief
- Round 2: Call **Nova Lite** with v1 + v2 code → get AGAINST-merge brief
- Round 3: Display verdict form (APPROVE / REJECT / REQUEST CHANGES)
- Display both briefs **side by side**

---

### ⏳ STEP 5 — Find & Reproduce the Bug
- Understand the hidden flaw in v2
- Write a 5-line Python script that reproduces it
- Write a DuckDB query that shows the data corruption

---

### ⏳ STEP 6 — Save verdict.json
```json
{
  "verdict": "REJECT",
  "reason": "v2 introduces duplicate rows when the function is called more than once.",
  "bug_found": true
}
```

---

### ✅ STEP 7 — Run & Demo

```bash
cd day9/team3_pipeline_lawyer
streamlit run app.py --server.port 8501
```

**App is LIVE at:** http://localhost:8501

**Demo walkthrough order:**
1. Open Case Brief → show v1 and v2 code
2. Click "Generate PRO-MERGE Argument" (Round 1 — Nova Pro)
3. Click "Generate AGAINST-MERGE Argument" (Round 2 — Nova Lite)
4. Show Side-by-Side briefs
5. Scroll to The Trap → explain the 5-line bug
6. Fill in Verdict → click Save
7. Show "What AI Got Wrong" section

---

## 📋 Pitch Structure (15 Minutes)

| Time | What to say |
|------|-------------|
| 0–2 min | Business problem — why idempotency matters |
| 2–8 min | Live demo of all 3 rounds |
| 8–11 min | The hidden bug you found + reproduction |
| 11–13 min | "What AI Got Wrong" — which brief was weaker |
| 13–15 min | Q&A |

---

*Updated as each step is completed.*
