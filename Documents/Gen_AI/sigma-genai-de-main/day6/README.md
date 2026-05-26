# Day 6 — SQL Brain
**AI-Powered SQL Review + NL2SQL Pipeline + dbt Scaffolding**

## What You Do Today

| # | Script | Run It | What Happens |
|---|--------|--------|--------------|
| 1 | `lab/1_sql_review.py` | `python 1_sql_review.py` | Feeds 3 broken SQL queries to AI → get JSON bug report |
| 2 | `lab/2_nl2sql_pipeline.py` | `python 2_nl2sql_pipeline.py` | English questions → SQL → validate → execute → answer |
| 3 | `lab/3_dbt_generator.py` | `python 3_dbt_generator.py` | AI scaffolds complete dbt project (models + tests + docs) |
| 4 | `lab/4_stretch_goal_sql_review.py` | `python 4_stretch_goal_sql_review.py queries/` | Batch-review + write your OWN broken query |

## How This Works

1. Read the mission briefing at the top of each `.py` file
2. Run the script
3. Read the code to understand HOW it works
4. Answer the AhaSlides quiz (proves you read it)
5. Validate → push

## Quick Start

```bash
cd repo/day6/lab
pip install -r requirements.txt

# Run each module in order:
python 1_sql_review.py          # creates review_report.json
python 2_nl2sql_pipeline.py     # creates nl2sql_audit.json
python 3_dbt_generator.py       # creates sigma_dbt/ folder
```

## Validate Your Work

```bash
cd repo/day6
python tests/validate_day6.py
```

Green = done. Red = run the script again. All core tests pass → push.

## Push

```bash
git add .
git commit -m "Day 6 done"
git push
```

## What Gets Checked

The validator verifies **output files exist** (you ran the scripts):
- `review_report.json` — Module 1 output (3 queries reviewed, issues found)
- `nl2sql_audit.json` — Module 2 output (5 questions processed)
- `sigma_dbt/` — Module 3 output (directory with 4 generated files)
- `validate_sql()` logic — safety checks work correctly

## Bonus

If you finish early: `bonus/` folder has a Snowflake Cortex Analyst lab.
Run the same 5 questions against Cortex and compare results.

## Streamlit Demo

Interactive GUI to experiment with all modules:
```bash
cd repo/day6/demo
streamlit run app.py
```
