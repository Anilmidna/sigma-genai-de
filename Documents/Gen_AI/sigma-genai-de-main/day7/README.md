# Day 7 — Pipeline Brain
**Spec-to-Ship in 45 Minutes**

## The Day in Order

| # | Activity | Time | What You Produce |
|---|----------|------|-----------------|
| 0 | Write your team's pipeline spec | 30–45 min | `lab/my_pipeline_spec.txt` (unique per team) |
| 1 | AI generates your pipeline | 10 min | `pipeline_brain/generated_pipeline.py` |
| 2 | AI generates your Airflow DAG | 10 min | `pipeline_brain/sigma_dag.py` |
| 3 | AI hardens your pipeline | 10 min | `pipeline_brain/hardened_pipeline.py` |
| 4 | Stretch: schema drift simulation | 30 min | `pipeline_brain/schema_drift_report.json` |
| 5 | Code review your generated pipeline | 45 min | `pipeline_brain/code_review.json` + your fixes |

## Step 0 — Write Your Spec First (do this before anything else)

Open `lab/0_team_spec_scenarios.md` → find your team's scenario → fill in the spec template → save as `lab/my_pipeline_spec.txt`

Module 1 will use YOUR spec if `my_pipeline_spec.txt` exists. Otherwise it falls back to the sample spec from `sample_data.py`.

Each team's pipeline output will be different. Your output files prove YOUR team ran it.

## Step 1–3 — Run in Order

```bash
cd repo/day7/lab

# Step 0 (before anything else):
# Fill in lab/0_team_spec_scenarios.md → save as lab/my_pipeline_spec.txt

# Then run modules in order:
python 1_spec_to_pipeline.py    # creates pipeline_brain/generated_pipeline.py
python 2_dag_generator.py       # creates pipeline_brain/sigma_dag.py
python 3_pipeline_hardening.py  # creates pipeline_brain/hardened_pipeline.py

# After modules 1-3, do Module 5:
python 5_code_review.py         # creates pipeline_brain/code_review.json
```

## How Each Module Works

1. Read the mission briefing at the top of each `.py` file
2. Do the **Manual First** exercise (2–5 minutes — attempt the task by hand before running)
3. Run the script
4. Read the generated code — understand HOW it works
5. Answer the AhaSlides quiz (proves you read it)

## Stretch Goal — Module 4

Runs standalone, no dependencies on Modules 1–3:

```bash
python 4_stretch_goal_schema_drift.py
```

After running: add `"refund_flag": "boolean"` to `DRIFTED_COLUMNS` in the script,
re-run, and observe how the AI handler responds to the third unexpected column.

## Validate Your Work

```bash
cd repo/day7
python tests/validate_day7.py
```

Green = done. Red = run the script again. All core tests pass → push.

## Push

```bash
git add .
git commit -m "Day 7 done"
git push
```

## What Gets Validated

The validator checks **output files exist** (you ran the scripts):

| Module | File | Minimum |
|--------|------|---------|
| 1 | `pipeline_brain/generated_pipeline.py` | > 500 bytes, contains PySpark |
| 1 | `pipeline_brain/generation_report.json` | valid JSON, has `generated_at` |
| 2 | `pipeline_brain/sigma_dag.py` | > 200 bytes, contains DAG |
| 2 | `pipeline_brain/dag_report.json` | valid JSON, has `tasks_found` |
| 3 | `pipeline_brain/hardened_pipeline.py` | > 500 bytes |
| 3 | `pipeline_brain/hardening_report.json` | valid JSON, `improvements_added` list |
| 5 | `pipeline_brain/code_review.json` | valid JSON, has `summary.merge_recommendation` |
| Stretch | `pipeline_brain/schema_drift_report.json` | valid JSON (SKIP if not run) |
| Stretch | `pipeline_brain/schema_evolution_handler.py` | exists (SKIP if not run) |

The following are **checked but not required to pass**:

| File | What it means |
|------|---------------|
| `pipeline_brain/fixed_pipeline.py` | You fixed at least 2 FAIL items from the code review |
| `pipeline_brain/my_review_notes.txt` | You documented what you changed |

## Platform Connection

```
Day 6  SQL Brain        →  dbt project + SQL review agent  (DONE)
Day 7  Pipeline Brain   →  pipeline_brain/  (YOU ARE HERE)
Day 8  DevOps Brain     →  tests + CI/CD for today's pipeline + automated code review on every PR
Day 12 Self-Heal Agent  →  reads run_metadata.json from this pipeline
```
