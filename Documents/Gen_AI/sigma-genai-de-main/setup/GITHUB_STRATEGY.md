# GitHub Workflow — GenAI Bootcamp
**Sigmoid Bangalore | Days 6–15 | Trainer: Anil Kumar**

---

## What's Changing

| Before (Days 1–5) | From Day 6 onward |
|---|---|
| Google Drive uploads | GitHub push |
| Screenshots as proof | Code as proof |
| Manual file naming | Just `git push` |
| No version history | Full git history |

**Why:** Less friction for students, better tracking for trainer, builds portfolio employers can see.

---

## How Fork Works (The Big Picture)

**Fork = full physical copy of your repo into student's account.**

```
┌──────────────────────────────────────────────────────────────────────┐
│                        GITHUB (cloud)                                 │
│                                                                      │
│   YOUR REPO                              STUDENT'S REPO              │
│   Anilmidna/sigma-genai-de              rahul/sigma-genai-de         │
│   ┌─────────────────────┐               ┌─────────────────────┐     │
│   │ day6/lab/            │    Fork       │ day6/lab/            │     │
│   │   sql_review.py     │──(copy)─────► │   sql_review.py     │     │
│   │   nl2sql_pipeline.py│               │   nl2sql_pipeline.py │     │
│   │                     │               │   review_report.json │ NEW │
│   │                     │               │   nl2sql_audit.json  │ NEW │
│   │ day7/ (pushed later)│               │                     │     │
│   └─────────────────────┘               └─────────────────────┘     │
│            │                                       ▲                  │
│            │ student pulls new days                 │ student pushes   │
│            └───────────────────────────────────────┘ results here    │
│                                                                      │
│   NOTHING comes back to your repo. Ever.                             │
│   You VIEW their repo using check_submissions.py                     │
└──────────────────────────────────────────────────────────────────────┘
```

**Key facts:**
- Fork = independent copy. Student owns it fully.
- Student's `git push` goes to THEIR repo only. Not yours.
- Student's `git pull upstream main` pulls NEW code from you (e.g., day7/ tomorrow).
- Your repo is never touched by students. It's read-only for them.
- You check their work by reading their fork (via GitHub API script).

---

## Repo Structure

**One repo for the entire bootcamp:**
```
github.com/Anilmidna/sigma-genai-de
├── setup/              ← requirements, env setup, check_submissions.py
├── day6/              ← pushed morning of Day 6
│   ├── README.md
│   ├── lab/           ← complete working code
│   ├── tests/         ← validator script
│   └── bonus/         ← optional extra lab
├── day7/              ← pushed morning of Day 7
...
└── day15/
```

Students fork this repo once. Pull every morning. Push every evening.

---

## One-Time Setup: Trainer

```bash
# Create the repo (already done if you're reading this)
gh repo create Anilmidna/sigma-genai-de --public --description "GenAI for Data Engineering — Sigmoid Bangalore 2026"

# Push initial content (setup + day6)
cd C:\Users\anilh\sigmoid\GenAI\repo
git init
git remote add origin https://github.com/Anilmidna/sigma-genai-de.git
git add setup/ day6/
git commit -m "Initial: setup + Day 6 materials"
git push -u origin main
```

---

## One-Time Setup: Students (Day 6 Morning, 5 min)

**Display on screen and walk them through:**

```bash
# Step 1: Fork (browser)
# Go to github.com/Anilmidna/sigma-genai-de → click "Fork" → Create Fork

# Step 2: Clone YOUR fork
git clone https://github.com/YOUR-USERNAME/sigma-genai-de.git
cd sigma-genai-de

# Step 3: Add trainer's repo as upstream
git remote add upstream https://github.com/Anilmidna/sigma-genai-de.git

# Step 4: Pull today's code
git pull upstream main

# Step 5: Verify
ls day6/lab/
```

---

## Trainer: Every Day

**Morning (before class):**
```bash
# Push today's folder
cd C:\Users\anilh\sigmoid\GenAI\repo
git add dayN/
git commit -m "Day N released"
git push origin main
```

**End of day (check who submitted):**
```bash
python setup/check_submissions.py 6
```

Output:
```
DAY 6 SUBMISSIONS (checked 2026-05-26 18:30)
──────────────────────────────────────────────────────────────────────
  ✓ rahul_sharma        — review_report.json ✓ | nl2sql_audit.json ✓ | stg_transactions.sql ✓
  ~ priya_nair          — review_report.json ✓ | nl2sql_audit.json ✓ | stg_transactions.sql ✗
  ✗ arun_kumar          — not submitted
──────────────────────────────────────────────────────────────────────
  TOTAL: 34 | SUBMITTED: 28 | COMPLETE: 25 | MISSING: 6
```

One command. Checks all 34 forks. Shows who did what. Run from laptop or Codespaces.

---

## Students: Every Day

**Morning (30 seconds):**
```bash
cd sigma-genai-de
git pull upstream main
ls dayN/lab/
```

**During class:**
```bash
cd dayN/lab
python script1.py     # Run it
python script2.py     # Read it — you WILL be quizzed
python script3.py
```

**End of day (30 seconds):**
```bash
python dayN/tests/validate_dayN.py    # All green?
git add .
git commit -m "Day N done"
git push
```

---

## What Proves Students Did the Work

| Proof | How |
|-------|-----|
| They ran the code | Output files exist (validator checks this) |
| They read the code | AhaSlides quiz, 10-sec timer, live in class |
| They pushed on time | `pushed_at` timestamp visible to trainer |

---

## Troubleshooting (Common Student Questions)

| Problem | Fix |
|---------|-----|
| Don't have GitHub account | github.com/signup (2 min) |
| `git clone` permission error | `gh auth login` or use HTTPS with token |
| Merge conflict on pull | `git stash && git pull upstream main && git stash pop` |
| Accidentally deleted files | `git checkout -- .` |
| Want to start fresh | `git fetch upstream && git reset --hard upstream/main && git push --force` |

---

## What Students Push (Changes Every Day)

Output file names are different per day — that's fine. The pattern is always:

```
dayN/lab/
├── script1.py          ← same for everyone (your code)
├── script2.py          ← same for everyone
├── output_file_1.json  ← GENERATED (proves they ran it)
├── output_file_2.json  ← GENERATED
└── output_folder/      ← GENERATED (if applicable)
```

Day 6 example: `review_report.json`, `nl2sql_audit.json`, `sigma_dbt/`
Day 7 will have different outputs. Validator always knows what to check.
