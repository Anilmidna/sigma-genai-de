# Activity 3 — Bug Hunt
## 5:30 PM – 6:15 PM | 45 minutes

---

## Setup (before 5:30 PM)

- Project the buggy code on Smart TV (below)
- Keep the Answer Key hidden — do not project
- Timer: set a visible countdown on screen (8 minutes)
  Use: https://www.timer.guru or just phone timer projected
- AhaSlides open and ready for reveal round

**Announce:**
> "This is code from our ingestion quality agent.
> It has 5 bugs. Some will kill the pipeline immediately.
> Some will corrupt data silently — the worst kind.
>
> 8 minutes. Teams write down the bugs they find.
> When timer ends — raise hand if you found all 5.
> We reveal one by one. One point per bug found.
> Bonus point if you explain WHY it breaks in production.
> Go."

---

## THE BUGGY CODE (project this on Smart TV)

```python
# Sigma DataTech — Ingestion Quality Agent
# Version: 1.0 | Last updated: 2026-06-02

import boto3, json, pandas as pd
from datetime import datetime

MODEL_ID = "amazon.nova-pro-v1:0"
REGION   = "us-east-1"

def call_bedrock(prompt):                                    # Line 9
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body   = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 1500, "temperature": 0.1},
    }
    resp = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    return json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"]


def load_data(file_path):                                   # Line 19
    df = pd.read_csv(file_path)
    return df


def run_quality_checks(df):                                 # Line 24
    results = []

    # Check 1: transaction_id not null
    null_mask = df["transaction_id"].isna()
    results.append({
        "check": "transaction_id_not_null",
        "failed_rows": df[null_mask].index.tolist(),
        "severity": "critical"
    })

    # Check 2: amount must be positive
    bad_amount = df[df["amount"] <= 0]
    results.append({
        "check": "amount_positive",
        "failed_rows": bad_amount.index.tolist(),
        "severity": "high"
    })

    return results


def auto_fix(df):                                           # Line 44
    # Fix null amounts with median
    median_val = df["amount"].median()
    df["amount"].fillna(median_val, inplace=True)
    return df


def quarantine_rows(df, failed_indices):                    # Line 51
    quarantine = df.loc[failed_indices].copy()
    clean      = df.drop(index=failed_indices)
    return clean, quarantine


def save_results(df_clean, df_quarantine, output_path):     # Line 57
    df_clean.to_csv(output_path, mode="a", index=False)     # Line 58
    df_quarantine.to_csv("quarantine.csv", index=False)


def generate_report(df, results, load_decision):            # Line 62
    report = {
        "timestamp":    datetime.now().isoformat(),
        "total_rows":   len(df),
        "load_decision":load_decision,
        "checks":       results,
    }
    with open("quality_report.json", "w") as f:
        json.dump(report, f)
    return report


# Main pipeline
def run_pipeline(file_path, output_path):                   # Line 74
    df        = load_data(file_path)
    df        = auto_fix(df)
    results   = run_quality_checks(df)

    all_failed = []
    for r in results:
        all_failed.extend(r["failed_rows"])

    df_clean, df_quarantine = quarantine_rows(df, all_failed)

    if len(df_quarantine) / len(df) > 0.2:
        load_decision = "reject_all"
    else:
        load_decision = "load_clean"

    save_results(df_clean, df_quarantine, output_path)
    report = generate_report(df, results, load_decision)

    print(f"Done. Clean: {len(df_clean)} | Quarantined: {len(df_quarantine)}")
    return report
```

---

## ANSWER KEY (keep hidden — reveal one by one)

---

### BUG 1 — Line 58: Append mode silently duplicates data
**The code:**
```python
df_clean.to_csv(output_path, mode="a", index=False)
```
**The bug:** `mode="a"` appends to the file instead of overwriting.
Every run adds more rows. Run it 10 times — you have 10x the data in Snowflake.

**Why it is the worst kind:** Pipeline shows green. No error. Dashboard numbers just slowly get bigger and nobody notices for weeks.

**The fix:** `mode="w"` — always overwrite. Or use Delta Lake MERGE for true idempotency.

**Prod impact:** Data duplication. Revenue reports inflated. Detected only during audit.

---

### BUG 2 — Line 9: No retry on Bedrock call
**The code:**
```python
resp = client.invoke_model(...)
```
**The bug:** One Bedrock timeout = entire pipeline crashes. No retry, no backoff, no fallback.

**Why it matters in prod:** Bedrock throttles during peak hours. 6 AM pipeline runs during AWS peak. This crashes silently 2-3 times per week.

**The fix:** Wrap in try/except with exponential backoff. 3 attempts, 1s/2s/4s waits.

**Prod impact:** Pipeline failure. On-call DE paged at 6 AM. 45-minute incident every time.

---

### BUG 3 — Line 44-47: Auto-fix runs BEFORE quality checks
**The code:**
```python
df = auto_fix(df)           # Line 75 — runs first
results = run_quality_checks(df)  # Line 76 — runs after
```
**The bug:** Auto-fix fills null amounts with median BEFORE the quality check runs.
The quality check for `amount_positive` now runs on the FIXED data — not the raw data.
Failed rows are never quarantined. They are silently loaded.

**Why it matters:** The check that was supposed to catch bad data runs after the data is already fixed. Quality report says "0 failures on amount" but the original data had 12 negative amounts.

**The fix:** Run quality checks first, then auto-fix only on non-critical failures.

**Prod impact:** Bad data loads to Snowflake. Quality report is lying. Silent corruption.

---

### BUG 4 — Line 24-26: Null check misses blank strings
**The code:**
```python
null_mask = df["transaction_id"].isna()
```
**The bug:** `isna()` only catches `None` and `NaN`. It does NOT catch empty strings `""`.
In the CSV, blank transaction_ids are stored as `""` not `NaN`.
The check passes. All blank PKs load to Snowflake.

**Why it matters:** This is exactly the issue we injected in the manual exercise.
Row 7 had `transaction_id = ""` — this code would not catch it.

**The fix:**
```python
null_mask = df["transaction_id"].isna() | (df["transaction_id"].astype(str).str.strip() == "")
```

**Prod impact:** Blank PKs in Snowflake. Joins fail. Lineage breaks. Compliance cannot audit.

---

### BUG 5 — Line 62-70: Report generated with ORIGINAL df, not clean df
**The code:**
```python
def generate_report(df, results, load_decision):
    report = {
        "total_rows": len(df),    # df = original full dataframe
        ...
    }
```
**The bug:** `generate_report` receives the original `df` (4,847 rows) not `df_clean` (4,806 rows).
Report says `total_rows: 4847` and `load_decision: load_clean`.
But only 4,806 rows were actually loaded.

**Why it matters:** The audit trail is wrong. If compliance asks "how many rows loaded?" — the report says 4,847 but Snowflake has 4,806. 41-row discrepancy. Unexplainable.

**The fix:** Pass `df_clean` and `df_quarantine` separately to the report function and report both counts explicitly.

**Prod impact:** Audit trail mismatch. Compliance finding. Potential regulatory issue.

---

## Scoring and Reveal (25 minutes)

**After 8-minute timer ends:**

Ask: "Raise your hand if your team found all 5."
Award: Teams that found all 5 get to reveal one bug each (keeps them engaged).

**Reveal round — one bug at a time:**

For each bug:
1. Show the line number
2. Read the bug description
3. Ask: "Which team had this one? Stand up."
4. Ask one team that missed it: "Why did you miss this one?"
5. Award 1 point per bug found, 1 bonus point for best prod impact explanation

**Tally:**

| Team | B1 | B2 | B3 | B4 | B5 | Total |
|---|---|---|---|---|---|---|
| Team 1 | | | | | | |
| Team 2 | | | | | | |
| ... | | | | | | |

---

## The One Line That Lands the Lesson

After revealing all 5 bugs, say:

> "Bug 3 is the most dangerous one. Not because it crashes.
> Because it does not crash. The pipeline runs green.
> The quality report shows zero failures.
> And 12 negative amounts just loaded to your Snowflake warehouse.
>
> The bugs that crash your pipeline are easy. You fix them and move on.
> The bugs that run green but corrupt your data silently —
> those are the ones that end careers.
>
> An AI agent generated this code. You just found 5 things it got wrong.
> That is your job. Not to write code. To know when the code is lying to you."

---

## Star Award

- 5/5 bugs found: 2 stars
- 4/5 bugs found: 1 star
- Best prod impact explanation (Anil's pick): 1 bonus star
- First team to find Bug 3 (the sneaky one): 1 bonus star
