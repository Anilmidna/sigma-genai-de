# NL2SQL vs Cortex Analyst — Sigma DataTech Evaluation

**Lab:** Day 6 Bonus — Cortex Analyst vs Module 2 NL2SQL Pipeline  
**Date:** 2026-05-25

---

## 5-Question Head-to-Head Results

| # | Question | Module 2 SQL Correct? | Cortex SQL Correct? | Module 2 Time | Cortex Time |
|:-:|---|:---:|:---:|:---:|:---:|
| 1 | Total transaction count | YES | YES | ~4.7s | ~95.4s |
| 2 | Failed transaction count | YES | YES | ~4.5s | ~43.0s |
| 3 | Highest revenue merchant | YES | YES | ~6.3s | ~25.0s |
| 4 | Failure rate by payment method | YES | YES | ~5.6s | ~25.0s |
| 5 | Total revenue (with COMPLETED filter) | YES | YES | ~4.3s | ~13.9s |

> **Key takeaway from timings:** Module 2 NL2SQL averaged **~5.1s per question**.
> Cortex Analyst averaged **~40.5s per question** — roughly 8× slower across this test set.
> Q1 (95.4s) likely hit a cold-start penalty on the Cortex COMPLETE endpoint;
> latency improved significantly by Q5 (13.9s) as the warehouse warmed up.

---

## Observations

### Where Module 2 NL2SQL was better

- **Speed — consistently faster.** Every single question answered in under 7 seconds (avg ~5.1s) vs Cortex's 14–95s range. For a self-serve analytics tool where business users expect near-instant responses, this gap is significant.
- **Predictable latency.** Module 2 variance was narrow (~4.3–6.3s). Cortex showed a 7× spread (13.9s–95.4s), making SLA guarantees harder.
- **No cold-start penalty.** The Nova Lite (Bedrock) model is always warm; Cortex COMPLETE via SQL appears to suffer warehouse or model cold-start overhead, especially noticeable in Q1 (95.4s).
- **Fine-grained prompt control.** You can inject business-specific phrasing, preferred output column names, or domain vocabulary directly into the system prompt — something the semantic YAML model does not expose at the same granularity.
- **Works outside Snowflake.** Module 2 can be wired to any database (Redshift, BigQuery, DuckDB) by swapping the executor. Cortex Analyst is tightly coupled to Snowflake.

---

### Where Cortex Analyst was better

- **Zero prompt engineering required.** No schema context string to write or maintain. The YAML semantic model is written once and Cortex handles the grounding — a major reduction in developer effort for onboarding new tables.
- **Semantic model = governed single source of truth.** Business rules (revenue = COMPLETED only), JOIN paths, and metric definitions live in a version-controlled YAML file — not buried inside a Python string that only the original developer knows about.
- **Business rule accuracy is structural, not probabilistic.** The `total_revenue` metric in the YAML hard-codes `WHERE STATUS = 'COMPLETED'`. Cortex *must* apply that rule; it cannot hallucinate a looser version of it. Module 2's rule accuracy depends on the LLM faithfully following the prompt instruction every time.
- **Data residency.** SQL generation, execution, and results never leave Snowflake — critical for regulated industries (BFSI, healthcare) where sending data payloads to an external API (Bedrock) violates compliance requirements.
- **Native multi-turn support.** The `messages[]` API pattern is built-in; our Module 2 multi-turn extension required custom `conversation_history` management (the stretch goal we just implemented).
- **Scales without code changes.** Adding a new table means adding a `tables:` block to the YAML. Module 2 requires updating `SCHEMA_CONTEXT`, rewriting few-shot examples, and retesting prompts.

---

### Business Rule Accuracy

> Question 5 is the **critical test** — revenue must only count COMPLETED
> transactions. Did both systems apply this rule correctly?

| System | Applied `STATUS = 'COMPLETED'` filter? | Notes |
|---|:---:|---|
| Module 2 NL2SQL | YES | Applied via `CASE WHEN STATUS = 'COMPLETED' THEN AMOUNT ELSE 0 END` as instructed in the schema context business rule. Correct — but depends on the LLM following the prompt every time. |
| Cortex Analyst | YES | Applied via the `total_revenue` metric in the semantic YAML: `SUM(CASE WHEN STATUS = 'COMPLETED' THEN AMOUNT ELSE 0 END)`. Structurally enforced — cannot be bypassed by rephrasing the question. |

> **Winner on reliability:** Cortex Analyst. Module 2 got it right here, but a slightly different question phrasing (e.g., *"total payments processed"*) could cause the LLM to skip the filter. Cortex's metric definition is immune to this — the rule is in the YAML, not in the prompt.

---

## Stretch Goal — Multi-Turn Conversation Results

> Run `python cortex_analyst.py demo` and record results here.
> This tests Cortex's contextual memory across follow-up questions.

| Turn | Question | Context Resolved Correctly? | Notes |
|:---:|---|:---:|---|
| 1 | Which merchant had the highest revenue? | YES | Returns   Zepto | 5485.49 as the top merchant with revenue amount; stored in `conversation_history` as the assistant turn. |
| 2 | How many of their transactions failed? | YES | "Their" is resolved from Turn 1's answer in the context block. Cortex generates a WHERE clause filtered to that specific merchant. It results 0 as the answer. |
| 3 | What payment method did those customers prefer? | YES | "Those customers" resolved via the merchant identified in Turns 1+2. Cortex generates a GROUP BY PAYMENT_METHOD filtered to that merchant's transactions. It results UPI with 4 payments.


**Conversation log saved to:** `conversation_results.json`

> **Observation:** The multi-turn feature works because `ask_cortex_conversational()` serialises prior Q&A results (column=value pairs) into the COMPLETE prompt. The model resolves pronouns ("their", "those") from this injected context. This is a meaningful step toward a production self-serve analytics chatbot.

---

## Your Recommendation

> Which approach would you deploy at Sigma DataTech for production self-serve
> analytics, and why?

### Decision Criteria

| Criteria | Module 2 NL2SQL | Cortex Analyst |
|---|---|---|
| **Setup effort** | ~200 lines Python + prompt engineering | YAML semantic model + API call |
| **Maintenance** | Update prompt for every new table/rule | Update YAML; Cortex re-reads at query time |
| **Accuracy (observed)** | 5/5 correct — prompt-dependent | 5/5 correct — structurally enforced via YAML |
| **Avg. response time** | ~5.1s (consistent) | ~40.5s (cold-start sensitive) |
| **Cost model** | Nova Lite (Bedrock) charges per token | Snowflake credit consumption (warehouse time) |
| **Data residency** | Data leaves Snowflake → sent to AWS Bedrock | Data stays entirely within Snowflake |
| **Scalability** | Maintain schema context manually per table | Semantic model scales; governed centrally |
| **Multi-turn chat** | Custom implementation (stretch goal added) | Native support via `messages[]` API |
| **Compliance fit** | ⚠️ External API — may violate data residency | ✅ Everything runs inside Snowflake boundary |

### Final Recommendation

**Recommended approach:** Hybrid — Cortex Analyst for production, Module 2 approach as a fallback/external channel

**Reason:**

For Sigma DataTech's **production self-serve analytics**, we recommend **Cortex Analyst** as the primary engine. Business rule accuracy is structurally guaranteed (not prompt-dependent), the semantic model is a single governed source of truth that scales without developer involvement, and data never leaves Snowflake — which is essential for a payment-processing company handling sensitive financial data. The current latency disadvantage (~40s avg) is a cold-start artifact of the lab's shared warehouse setup; in a production environment with a dedicated warehouse kept warm, this gap narrows significantly.

We retain the **Module 2 NL2SQL approach** as a secondary channel for scenarios where Snowflake is unavailable, where Bedrock latency is acceptable, or where stakeholders need rapid ad-hoc queries from outside the Snowflake ecosystem (e.g., from a web dashboard backed by a different DB). The main trade-off we accept with Cortex as primary is vendor lock-in to Snowflake and the need to invest in YAML model curation — both of which are manageable given the maintenance cost savings compared to ongoing prompt engineering.

---

## Appendix — Raw Results

> Link to or embed the raw output files for full reproducibility.

- **Cortex results JSON:** [`cortex_results.json`](./cortex_results.json)
- **Conversation log JSON:** [`conversation_results.json`](./conversation_results.json)
- **Semantic model YAML:** [`sigma_semantic_model.yaml`](./sigma_semantic_model.yaml)
- **Cortex Analyst script:** [`cortex_analyst.py`](./cortex_analyst.py)
- **NL2SQL Pipeline script:** [`../lab/2_nl2sql_pipeline.py`](../lab/2_nl2sql_pipeline.py)
- **NL2SQL Audit log:** [`../lab/nl2sql_audit.json`](../lab/nl2sql_audit.json)
