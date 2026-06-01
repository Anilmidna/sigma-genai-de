# Chaos Log — Team Name: _______________
## Day 13 | Wednesday 4 June 2026

Fill this in DURING Phase 2. Save and push before lunch.
Be specific. Vague answers = incomplete.

---

## Injection 1 — Schema Drift

**What broke:**
(Which stage failed? Bronze / Silver / Gold / dbt / Snowflake? What was the error message?)


**Root cause (one sentence):**


**Fix applied:**
(What exactly did you change in the code?)


**Proof it works:**
(What is the Snowflake row count AFTER your fix?)


**Time taken to fix:** _____ minutes

---

## Injection 2 — PII Leak

**Columns found:**
(List the exact column names that contain PII)


**How you found them:**
(Column name scan / sample value check / other?)


**Masking applied:**
(Which masking method? Show one masked example value)


**Did you miss any column?**
(Be honest — if you missed one, say which one and why)


**Why regex alone would NOT catch `cust_ph`:**
(One sentence)


---

## Injection 3 — Data Quality Rot

**Total records received:** 300

**Records dropped (quarantined):** _____

**Records loaded to Silver:** _____

**Four quality filters you added:**
1.
2.
3.
4.

**Snowflake GMV before fix:** _____ (was it negative?)

**Snowflake GMV after fix:** _____ (confirm all positive)

**Why this matters for a fintech business:**
(One sentence — what would the business see if you did NOT fix this?)

---

## Your Honest Reflection

**Which injection hurt the most? Why?**


**What would have happened if this hit a real prod pipeline at 2 AM?**


**One thing you would add to the pipeline to prevent this in future:**


---

*This file is pushed to your GitHub fork and visible in check_submissions.py*
*Incomplete answers are flagged automatically*
