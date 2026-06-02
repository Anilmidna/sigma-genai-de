# Architecture Decisions — Why We Built It This Way
## Sigma Intelligence Platform | Design Rationale

> Every system you build is a set of decisions.
> Most freshers learn WHAT was built. Senior engineers ask WHY.
> This document explains the ten most important decisions in this platform —
> what we chose, what we rejected, and what breaks in production if you get it wrong.

---

## 1. Why Agents Instead of Step Functions or Airflow?

**One sentence:** Workflow orchestration executes a graph you designed. Agents navigate a problem space you didn't fully anticipate.

**The explanation:**

Step Functions, Airflow, and Prefect are excellent tools. You draw a directed graph at design time — every node, every branch, every failure path. The system executes exactly what you drew. Predictable, cheap, auditable.

The problem: the failure in this lab was a field rename (`merchant_name` → `merchant_nm`) causing Snowflake COPY INTO to silently load zero rows. No errors. Lambda green. Firehose green. S3 has files. There is no Step Functions branch for "everything looks healthy but GMV is zero — go correlate Lambda version history with Snowflake query history across a 4-minute window."

The Forensics Agent found it because it reasoned. It observed the evidence, formed a hypothesis, tested it, and confirmed it. That is not branching logic. It is inference over an open-ended input space.

**When Step Functions is the RIGHT choice:**
- Known, repeatable tasks: trigger dbt run, backfill a partition, send a daily report
- Compliance-critical sequences where every step must be logged and approved
- High-frequency operations where 1-3 seconds of LLM latency per step is unacceptable

**When Agents are the RIGHT choice:**
- The root cause space is too large to enumerate in advance
- The task requires judgment — not just execution — based on what is observed
- The environment changes faster than you can redeploy a workflow graph

**The architecture:** Use both. Agent investigates and returns a structured `root_cause` JSON. Step Functions picks it up and executes the fix deterministically. Agents at the decision boundary. Workflows at the execution boundary.

---

## 2. Why a Supervisor + 6 Specialists Instead of One Big Agent?

**One sentence:** One agent doing everything is a monolith. Six specialists in parallel is a distributed system.

**The explanation:**

You could prompt a single Nova Pro agent: "Here is the incident. Investigate, calculate impact, recover data, rollback Lambda, create alarms, and write a report." It would try. It would also mix contexts, lose track of findings, and produce a confused result 30% of the time.

Specialists solve three problems simultaneously:

**1. Context isolation.** The Forensics Agent's prompt is entirely about log correlation. It does not know about SLA contracts. The Impact Agent knows nothing about Kinesis shard iterators. Each agent's context window contains only what it needs — which means it reasons better and hallucinates less.

**2. Parallel execution.** Forensics and Impact run simultaneously. If they ran sequentially, the 26-second recovery becomes 60+ seconds. In a production SLA breach, every second matters.

**3. Debuggability.** When something goes wrong, you know which agent failed and why. A single monolithic agent gives you one confused output. A 6-agent system gives you 6 independent traces, each auditable.

**The production reality:** Specialist agents cost more (6 LLM calls vs 1). The right threshold: if the task has more than 2-3 conceptually distinct phases, split into specialists. If it is a simple linear task, one agent is enough.

---

## 3. Why MCP (Runtime Tool Discovery) Instead of Hardcoding Tools in Each Agent?

**One sentence:** Hardcoded tools are compiled in. MCP tools are discovered at runtime — the difference between a static binary and a plugin system.

**The explanation:**

Every Bedrock agent has an Action Group — a list of tools it can call. You could hardcode these at agent creation: "Forensics gets check_cloudwatch, get_kinesis_records, query_snowflake." Done.

The problem: six months later, your team adds a new tool — `check_databricks_job_status`. With hardcoded tools, you update every agent individually. With MCP, you add the tool to the registry and every agent discovers it on the next invocation. No agent code changes needed.

In this lab, the MCP server exposes a `/tools` endpoint. The Supervisor queries it at the start of every run. Add `query_glue_catalog` to `TOOLS` in `sigma_mcp_server.py` and the Supervisor can use it immediately — without touching any agent configuration.

**The production reality:** MCP adds one network hop per invocation. For latency-sensitive pipelines, the discovery overhead (< 100ms) is negligible. The architectural payoff — a tools layer that evolves independently from the agents layer — is worth it at any serious scale.

**What the interviewer wants to hear:** "We separated tool definitions from agent definitions so that the tool surface can grow without requiring agent redeployment. This is the same reason microservices have APIs — the contract is stable, the implementation can change."

---

## 4. Why RAG + Knowledge Base Instead of Putting Everything in the System Prompt?

**One sentence:** A system prompt is static and has a size limit. A Knowledge Base is dynamic, searchable, and gets smarter with every incident.

**The explanation:**

You could embed every SLA contract, every runbook, and every past incident directly into the Supervisor's system prompt. For the first incident, this works. By the tenth incident, you have 50,000 tokens of context — slow, expensive, and the agent starts ignoring the early parts of the prompt (the "lost in the middle" problem).

RAG (Retrieval-Augmented Generation) retrieves only what is relevant to the current query. When the Impact Agent asks "what is QuickMart's SLA threshold?", the Knowledge Base searches the SLA contract collection and returns the relevant clause — not the entire 15-page PDF.

More importantly: the Knowledge Base accumulates. Every incident report written today is retrieved tomorrow. On the first run of this lab, the agent has no prior incidents. On the tenth run of the same failure, it retrieves today's report and says: "This matches the pattern from 4 June 2026 — Lambda version change caused schema drift. Applying the same fix." That is institutional memory at machine speed.

**The production reality:** Bedrock Knowledge Base uses OpenSearch Serverless, which has a minimum cost (~$350/month). For a startup, a self-hosted ChromaDB is cheaper. For an enterprise, the managed service is worth it for the SLA, security, and zero operational overhead.

---

## 5. Why MERGE INTO Instead of INSERT — Idempotency Is Not Optional

**One sentence:** INSERT creates duplicates when you replay. MERGE ON primary key makes replay safe to run ten times.

**The explanation:**

The Recovery Agent replays 847 Kinesis records into Snowflake. If it uses `INSERT INTO`, every replay adds 847 more rows — a failed and retried recovery creates 1,694 rows, then 2,541, then 3,388. The GMV figure doubles. The merchant gets billed twice. The SLA breach gets worse.

`MERGE INTO ... ON transaction_id` checks: "Does this record already exist?" If yes, skip. If no, insert. Running the recovery ten times produces exactly 847 rows. Every time.

This guarantee is called **idempotency** — the property that applying an operation multiple times produces the same result as applying it once. In data engineering, idempotency is not a nice-to-have. It is a requirement for any pipeline that can fail and retry.

**The rule:** Every pipeline that writes to a data store must be idempotent. If it is not, a retry makes the data wrong. And retries happen — at 3 AM, during chaos, when the on-call engineer fat-fingers a command.

**What breaks without it:** On the day this actually matters in production, you will not know the pipeline ran twice. You will see inflated GMV, confuse it with a revenue spike, and report it upward. The correction will be painful.

---

## 6. Why Bedrock Guardrails Instead of Trusting the Prompt to Behave?

**One sentence:** A prompt is a suggestion. A Guardrail is a policy. Suggestions get ignored under adversarial conditions. Policies don't.

**The explanation:**

You could write in the system prompt: "Never generate SQL that contains DROP, DELETE, or TRUNCATE." Effective 95% of the time. The remaining 5% — when the agent receives a carefully crafted input, or hallucinates under pressure — it ignores the instruction.

Bedrock Guardrails sit between the agent and the LLM as a separate enforcement layer. The agent sends a prompt. Guardrails intercept it. If the response contains a DROP TABLE statement, Guardrails redact it and return a blocked response — before the agent ever sees the output.

In this lab, Guardrails enforce three things:
- **PII redaction** — phone numbers and account numbers in data samples are masked before the LLM processes them
- **Topic denial** — any instruction to DROP, DELETE, or TRUNCATE a table is blocked
- **Grounding** — agent responses must cite retrieved data, not invent facts

In a regulated fintech like Sigma DataTech, a data leak through an LLM response is a SEBI reportable incident. A compliance fine. A news story. Guardrails are not optional — they are the difference between a prototype and a production system.

**What the interviewer wants to hear:** "We applied defence in depth — the prompt instructs, the Guardrail enforces, and the IAM policy prevents. No single layer is trusted alone."

---

## 7. Why Lambda for Tool Functions Instead of Agents Calling AWS APIs Directly?

**One sentence:** The Lambda is the abstraction layer. Without it, your agent is coupled to every AWS API signature change forever.

**The explanation:**

The Forensics Agent needs to check CloudWatch metrics. Option A: give the agent an IAM role and let it call `cw.get_metric_statistics()` directly. Option B: wrap that call in a Lambda function, give the agent permission to invoke the Lambda.

Option A seems simpler. It breaks in four ways:

**1. IAM explosion.** To call CloudWatch, Kinesis, Snowflake, Lambda, S3, and SNS directly, the agent's IAM role needs broad permissions across 6 services. With Lambda wrappers, the agent only needs `lambda:InvokeFunction` on 9 specific functions. Minimum privilege.

**2. Coupling.** AWS changes the CloudWatch API response format. With Option A, you update the agent prompt. With Lambda, you update one function — the agent never changes.

**3. Testability.** You can invoke `sigma-tool-check-cloudwatch` locally with a test event. You cannot easily test "what the agent does with a CloudWatch response" without running the full agent.

**4. Reusability.** The same `query_snowflake` Lambda is called by the Impact Agent, the Recovery Agent, and the Rollback Agent. Logic in one place. Three callers. No duplication.

**The production reality:** This is the same reason you don't let your frontend call the database directly. The API layer (Lambda, in this case) is the contract. The implementation behind it can change.

---

## 8. Human-in-the-Loop — When to Require Approval, When to Let the Agent Act

**One sentence:** Automate the reversible. Require approval for the irreversible.

**The explanation:**

This lab lets the Recovery Agent replay Kinesis records and load them to Snowflake autonomously — and the Hardening Agent create CloudWatch alarms autonomously. This is intentional for a classroom demo. In production, some of these actions require human approval.

**Classify every agent action by risk:**

| Action | Risk | Correct Pattern |
|---|---|---|
| Check CloudWatch metrics | None — read only | Fully autonomous |
| Query Snowflake | None — read only | Fully autonomous |
| Send SNS alert | Low — reversible (alerts can be ignored) | Autonomous |
| Create CloudWatch alarm | Medium — can cause alert fatigue | Recommend → human approves |
| Replay Kinesis records (MERGE) | Medium — idempotent, safe to re-run | Autonomous with audit log |
| Apply schema fix (ALTER TABLE) | High — affects all downstream consumers | REQUIRE human approval |
| Lambda rollback | High — changes production code path | Require human approval |
| Quarantine records | High — data is removed from main flow | Autonomous with quarantine log + human review within 24h |

**The pattern for high-risk actions:** Agent generates a structured `action_proposal` JSON with the proposed action, the justification, and the predicted impact. This is written to an approval queue (SNS + Lambda, or Slack webhook). A human approves or rejects within a configurable timeout. If no response within the timeout — default to safe (do not act).

**The one sentence:** "The agent should be as autonomous as the reversibility of its actions allows."

---

## 9. Why SNS Push Alerts Instead of Polling Logs?

**One sentence:** Polling checks periodically. SNS notifies immediately. The difference is the 7 hours between 02:11 AM (when the pipeline broke) and 09:03 AM (when the analyst noticed).

**The explanation:**

The silent disaster in this lab lasted 7 hours because no alert fired. The existing CloudWatch alarm threshold was too high. No one was polling the pipeline health — they were waiting for a business analyst to notice at 9 AM.

SNS (Simple Notification Service) is a push system. When an event occurs — SLA breach confirmed, pipeline restored, new alarm created — the agent publishes to an SNS topic. Every subscriber (email, Slack webhook, PagerDuty) receives the message within seconds.

**Push vs Pull:**

| Approach | Latency | Cost | Scales to |
|---|---|---|---|
| Poll CloudWatch every 5 min | 5 min worst case | Low | Works for low-frequency checks |
| CloudWatch Alarm → SNS | Seconds | Near zero | Recommended for all production pipelines |
| Agent publishes to SNS on finding | Seconds | Near zero | What this lab does |
| Business analyst checks dashboard | Hours | Human time | What broke Sigma DataTech |

**The production reality:** Every SLA-bound data pipeline should have at minimum: (1) a CloudWatch alarm for zero-row loads, (2) SNS notification for the on-call engineer, and (3) an automated health check that runs every 15 minutes and publishes to a status dashboard. This lab creates the alarm and SNS. The health check is your Bonus Challenge.

---

## 10. Why 6 Specialist Agents Instead of 1 Generalist Agent Doing All 6 Jobs?

*(Expanded from Decision #2 — the specific tradeoffs)*

**One sentence:** A generalist does everything adequately. A specialist does one thing correctly. In a regulated environment, "adequately" is not good enough.

**The Forensics Agent's prompt is 800 words** — entirely about log correlation, timeline reconstruction, and root cause hypothesis formation. It knows what a "Lambda alias" is, what "Firehose DataFreshness" means, and how to correlate timestamps across CloudWatch, Kinesis, and Snowflake.

If you merge Forensics + Impact + Recovery into one agent, the prompt becomes 2,400 words. The agent's attention is divided. It starts making trade-offs — spending tokens on impact calculation while the forensics reasoning is still incomplete. The output quality drops in ways that are hard to detect until something goes wrong.

**The SLA breach calculation requires precision.** The Impact Agent compares ₹1,21,450 (QuickMart's missing GMV) against ₹50,000 (the SLA threshold from the PDF) and confirms a breach. This requires: reading the SLA PDF via RAG, parsing the threshold, calculating the GMV gap, and making a binary determination. A generalist agent doing this while simultaneously diagnosing root cause and planning recovery will make errors.

**The counter-argument (when you should NOT split):**
- 6 agents = 6 LLM calls = 6× the cost and latency of 1 agent
- For simple incidents, the overhead is not worth it
- A startup with 1,000 transactions/day can use 1 generalist agent — the savings matter more than the precision

**The rule:** Split into specialists when (a) the tasks are conceptually distinct, (b) precision in each domain matters more than overall cost, and (c) parallel execution provides a meaningful latency reduction.

---

## The Question That Ties All 10 Together

> *"You have spent 13 days learning to use AI. The most important thing is not knowing the tools — it is knowing when to use them and when not to.*
>
> *Every decision above has a "when not to" answer. A senior engineer's value is in recognising the boundary — where the tool helps and where it introduces complexity, cost, or risk that a simpler solution would avoid.*
>
> *When you join your first job, you will be tempted to add agents, RAG, and Guardrails to every problem. Resist that temptation. The best engineers reach for the simplest tool that solves the problem correctly. Complexity is a liability you pay for every day, forever."*

---

*Sigma DataTech · Architecture Decisions · Day 12*
