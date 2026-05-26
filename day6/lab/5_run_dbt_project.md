# Mission: Run the dbt Project You Generated
**Day 6 · Module 4 · Sigma Intelligence Platform**

---

## Mission Brief

In Module 3 you used AI to scaffold a complete dbt project in 60 seconds. That project is sitting on your machine — but it has never run. Generated code that has never executed is not an asset, it is a liability.

Your mission: get it running. Fix what AI got wrong. Make `dbt test` pass — including the one test that is *supposed* to fail on bad data.

This is what a senior analytics engineer does with AI output. Not admires it. Runs it.

---

## What You Will Learn

- How to connect dbt to Snowflake using a `profiles.yml` file
- The difference between `dbt run` (transforms data) and `dbt test` (validates data)
- How to read a dbt error and trace it back to a broken `ref()` or `source()` call
- Why a failing test is a good thing — it means your data contract caught something real

---

## Manual-First Exercise (5 minutes)

Before doing anything, open these two files and read them carefully:

- `sigma_dbt/models/staging/schema.yml`
- `sigma_dbt/models/marts/schema.yml`

Answer these questions on paper before you run a single command:

1. What database and schema does the `source()` point to?
2. Which column has a `unique` test on it?
3. Which test do you think will **fail** — and why?

Write your answers down. You will check them against what actually happens.

---

## Pre-requisites

- dbt Core installed: `pip install dbt-snowflake`
- `sigma_dbt/` folder exists in your `day6/lab/` directory (generated in Module 3)
- Your `student_key.p8` file is in `day6/bonus/`

---

## Steps

### Step 1 — Create your dbt profile

dbt connects to Snowflake via a `profiles.yml` file in your home directory.

Create the file at `~/.dbt/profiles.yml` (Windows: `C:\Users\<yourname>\.dbt\profiles.yml`):

```yaml
sigma_dbt:
  target: dev
  outputs:
    dev:
      type: snowflake
      account: GEJKIOG-TKC55632
      user: student_genai
      private_key_path: C:\Users\<yourname>\path\to\student_key.p8
      role: STUDENT_CORTEX
      database: SIGMA_DE
      warehouse: COMPUTE_WH
      schema: PUBLIC
      threads: 1
```

Replace `<yourname>` and the key path with your actual values.

---

### Step 2 — Check the dbt project config

Open `sigma_dbt/dbt_project.yml`. Confirm the profile name matches:

```yaml
profile: sigma_dbt
```

If the file does not exist, create it:

```yaml
name: sigma_dbt
version: '1.0.0'
profile: sigma_dbt
model-paths: ["models"]
models:
  sigma_dbt:
    staging:
      materialized: view
    marts:
      materialized: table
```

---

### Step 3 — Test the connection

```bash
cd sigma_dbt
dbt debug
```

Expected: `All checks passed` at the bottom.

If you see a connection error — check your account ID and key path in `profiles.yml`.

---

### Step 4 — Run the staging model

```bash
dbt run --select staging
```

Read the output carefully. If it fails, the error message will tell you exactly which line in the SQL is wrong.

**Common AI mistake to look for:** `source('sigma_analytics', 'fact_transactions')` — the database name `sigma_analytics` may be wrong. The actual database is `SIGMA_DE`. Fix it in `schema.yml` and re-run.

---

### Step 5 — Run the mart model

```bash
dbt run --select marts
```

This runs `mart_merchant_performance.sql`. If it fails with `Object does not exist`, check that the `ref()` call points to the exact model name from Step 4.

**Common AI mistake to look for:** `ref('transactions')` instead of `ref('stg_transactions')`. Fix and re-run.

---

### Step 6 — Run all tests

```bash
dbt test
```

You will see a mix of PASS and FAIL. This is expected.

For each FAIL, read the message and answer:
- Is this a bad test (AI wrote it wrong)?
- Or is this real bad data the test correctly caught?

One test is deliberately designed to catch bad data with `STATUS='CANCELLED'`. When it fails — that is the test doing its job. Do not fix that test.

---

### Step 7 — Run everything together

```bash
dbt build
```

`dbt build` = `dbt run` + `dbt test` in one command. This is what CI/CD runs on every PR.

---

## Validation

You are done when you can show:

```
dbt run   → at least 2 models with status: OK
dbt test  → at least 3 tests PASS + 1 deliberate FAIL visible
```

Screenshot your terminal output and keep it — it is evidence for your push.

---

## Debrief

**What just happened:** You ran AI-generated dbt code against a real Snowflake database. The AI gave you a working scaffold — but with at least one wrong `source()` database name and one wrong `ref()` model name. You found them, fixed them, and got the project running. That review-and-fix loop is the job.

**What AI got right:** Model structure, CTE patterns, test selection (`not_null`, `unique`, `accepted_values`) — all correct. The scaffold would have taken a junior DE 2+ hours to write from scratch.

**What AI got wrong:** `source()` database names (AI guesses from the schema description, not from your actual Snowflake account). `ref()` names (AI sometimes uses the table name instead of the model name). These are predictable, repeatable mistakes — which means you now know exactly what to check every time.

**The rule to remember:** AI generates the scaffold. You own the integration. The bugs are always at the boundaries — where AI-generated code meets your real environment.

**Where this fits next:** On Day 8, CI/CD will run `dbt build` automatically on every pull request. The failing test you saw today becomes a gate that blocks bad code from reaching production.

---

## Bonus Challenge

The mart model calculates `failure_rate_pct`. Add a new dbt test that checks this value is always between 0 and 100. Write the YAML by hand — do not use AI for this one. Then run `dbt test` to confirm it passes.
