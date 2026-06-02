# Sigma Command Center — Stretch Challenge
## Build a Business Dashboard for the Intelligence Platform

**Time:** 60 minutes | **Teams:** All | **Tools:** Any AI (Claude, ChatGPT, Cursor, Copilot)

---

## Mission Brief

Your agents just recovered 824 missing records in 26 seconds.
The analytics manager knows it happened — but she cannot see it.

She sees a terminal. She needs a dashboard.

Your job: build the **Sigma Command Center** — the business-facing view of everything
your agents just did. Not an engineering trace (that's Langfuse). A command center
that a non-technical manager can read and trust.

When you are done, you will deploy it to **AWS App Runner** so anyone in the room
can open it on their phone. That is a live cloud app — built and shipped in 60 minutes.

---

## Functional Requirements

Your dashboard must have all 7 sections:

### 1. KPI Cards (top of page)
Six metrics displayed as large cards:
- **Expected Transactions** — what the dashboard should have shown (1,20,000)
- **Actual Transactions** — what it actually showed (40,000)
- **Missing Transactions** — the gap (80,000)
- **Recovered Records** — records the Recovery Agent restored (824)
- **Quarantined Records** — records with data quality issues (23)
- **Recovery Time** — seconds from trigger to full recovery (26s)

### 2. Agent Status Panel
One status indicator per agent — shows whether each completed, is running, or failed:
- Supervisor, Forensics, Impact, Recovery, Hardening, Reporting

Each card must show: agent name, status (complete / running / failed), and one-line finding.

### 3. Incident Timeline
Chronological list of events from the incident.
Each event has a timestamp, description, and severity (critical / warning / info / success).
Use colour or icons to distinguish severity.

### 4. Root Cause Panel
A clearly highlighted block showing:
- What broke and when
- Why it was a silent failure (no errors, no alerts)

### 5. Recovery Summary
- Records restored vs quarantined (use a progress bar or chart)
- Confirmation that idempotency was applied (no duplicates)
- Recovery duration

### 6. Prevention Measures
The 3 CloudWatch alarms the Hardening Agent created — name, trigger condition, current state.

### 7. Incident Report Viewer
The full incident report rendered as readable text (not raw markdown).
Put this in a collapsible section at the bottom.

---

## Technical Specification

### Technology Stack
| Layer | Tool |
|---|---|
| UI Framework | Streamlit |
| Language | Python 3.10+ |
| Data | Your team's S3 bucket + CloudWatch (Phase 3 output) |
| Deployment | AWS App Runner via Amazon ECR |

### Data Sources — Already in Your S3 Bucket from Phase 3

| Data | S3 Path | What it contains |
|---|---|---|
| Incident report | `reports/incident_YYYYMMDD_HHMMSS.md` | Root cause, timeline, business impact, fix applied |
| Quarantined rows | `quarantine/quarantine_*.csv` | Records the Recovery Agent could not load |
| Alarm state | CloudWatch API (boto3) | 3 alarms the Hardening Agent created |

Your dashboard reads these files directly. No dummy data, no placeholder JSON.
What you see in the dashboard is what your agents actually did.

### Architecture
```
Phase 3 completed → real output in your S3 bucket:
  reports/incident_*.md
  quarantine/quarantine_*.csv
  CloudWatch: 3 alarms live

Your Streamlit dashboard reads these directly:
  S3 + CloudWatch ──→ app.py ──→ Browser

Deployment:
  app.py → Dockerfile → ECR → App Runner → Public URL
```

### Langfuse vs This Dashboard
| Langfuse | Sigma Command Center |
|---|---|
| AI observability — traces, prompts, tool calls | Business view — KPIs, recovery proof, alarms |
| For the DE team debugging the agents | For the analytics manager and CTO |
| Already live from Phase 3 | You are building this now |

Do NOT overlap with Langfuse. Your dashboard is the business layer.

---

## What You Should Do — Step by Step

### Phase A — Set Up (5 minutes)

**Step 1:** Create a new folder called `dashboard/` inside your team's repo.

**Step 2:** Create `requirements.txt` with the packages you need.
At minimum: `streamlit`, `boto3`, `pandas`, `python-dotenv`.

**Step 3:** Confirm your `.env` file has `SIGMA_S3_BUCKET` set — your app reads from this bucket.
Phase 3 already wrote the incident report and quarantine file there.

**Step 4:** Confirm Streamlit runs on your machine:
```bash
pip install streamlit
streamlit hello
```
If you see the Streamlit demo page in your browser — you are ready.

---

### Phase B — Build the Dashboard (35 minutes)

**Step 5:** Create `app.py`. Use any AI tool to scaffold it.

Give the AI this prompt (or your own version):
> *"Build a Streamlit dashboard called Sigma Command Center.
> It reads from AWS S3 using boto3. The bucket name comes from the
> environment variable SIGMA_S3_BUCKET. It reads the latest markdown file
> from the `reports/` prefix and the latest CSV from the `quarantine/` prefix.
> It also reads CloudWatch alarm states for alarms named
> sigma-snowflake-zero-load, sigma-lambda-version-change,
> sigma-pipeline-row-divergence.
> Show: incident summary KPIs, root cause, fix applied, CloudWatch alarms,
> quarantine table, and the full incident report as markdown.
> Wide layout. Professional look."*

**Step 6:** Run your app and check every section:
```bash
streamlit run app.py
```
Open `http://localhost:8501`. You should see your team's real Phase 3 data.

**Step 7:** For each of the 7 required sections — confirm it shows real data from S3.
If a section shows an error, check your `.env` has `SIGMA_S3_BUCKET` set correctly.
If the incident report section is empty — Phase 3 may not have completed. Re-run the supervisor trigger.

---

### Phase C — Deploy to AWS App Runner (15 minutes)

This is new learning. You have used EC2 (DE batch) and Lambda (this batch).
App Runner is the third way: give it a Docker container, get a public HTTPS URL in 3 minutes.

**Step 9:** Create a `Dockerfile` in your `dashboard/` folder.
It must do four things: start from a Python base image, copy your files in,
install requirements, and start the Streamlit app on port 8501.
Ask any AI to write this for you — describe what it needs to do.

> **Important — the container has no AWS credentials by default.**
> Your Dockerfile COPYs `app.py` and `requirements.txt` into the container.
> AWS credentials for S3 access are provided at runtime via App Runner
> (IAM role or environment variables — see Step 14). Do NOT hardcode credentials.

**Step 10:** Build your Docker image locally and confirm it works:
```bash
docker build -t sigma-command-center .
docker run -p 8501:8501 sigma-command-center
```
Open `http://localhost:8501` — same dashboard, now running in a container.
If it shows the dashboard in demo mode — the image is correct. Move on.

**Step 11:** Authenticate Docker to Amazon ECR:
```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  <your-account-id>.dkr.ecr.us-east-1.amazonaws.com
```

**Step 12:** Create an ECR repository for your image:
```bash
aws ecr create-repository \
  --repository-name sigma-command-center \
  --region us-east-1
```

**Step 13:** Tag your image and push it to ECR:
```bash
docker tag sigma-command-center:latest \
  <your-account-id>.dkr.ecr.us-east-1.amazonaws.com/sigma-command-center:latest

docker push \
  <your-account-id>.dkr.ecr.us-east-1.amazonaws.com/sigma-command-center:latest
```

**Step 14:** Create an App Runner service.
Go to **AWS Console → App Runner → Create service**.

*Source:*
- Source: Container registry → Amazon ECR
- Image URI: your ECR image URI from Step 13
- Port: **8501** ← Streamlit's port. Most web apps use 8080 — this is different.
- CPU: 0.25 vCPU / Memory: 0.5 GB

*S3 connectivity — choose one:*

**Option A — IAM Instance Role (correct way, same pattern as your Lambda tools):**
- Under **Security** → Instance role → Create new role
- Attach policy: `AmazonS3ReadOnlyAccess` + `CloudWatchReadOnlyAccess`
- The container automatically uses this role. No credentials in code.
- This is how every production AWS app authenticates — not keys, roles.

**Option B — Environment variables (faster for the classroom demo):**
- Under **Configure service** → Environment variables → Add:

  | Key | Value |
  |---|---|
  | `AWS_ACCESS_KEY_ID` | your access key |
  | `AWS_SECRET_ACCESS_KEY` | your secret key |
  | `AWS_DEFAULT_REGION` | `us-east-1` |
  | `SIGMA_S3_BUCKET` | `sigma-datatech-yourteam` |

- boto3 inside the container reads these at runtime and connects to S3.

> **Recommendation for the classroom:** Use Option A (IAM role) — same pattern as
> the Lambda execution role from Phase 1. Your team already knows this pattern.
> Option B works if you're short on time.

Click **Create and deploy**.

**Step 15:** Wait ~3 minutes. When status shows **Running**, click the service URL.
Your dashboard is live at `https://xxxxxx.us-east-1.awsapprunner.com`.
Share this URL in the class chat — open it on your phone.

Your dashboard is now live at `https://xxxxxx.us-east-1.awsapprunner.com`.
Share this URL in the class chat. Everyone can open it on their phone.

---

### Phase D — Demo (5 minutes)

**Step 16:** Open your dashboard URL on the projector.
Walk through each of the 7 sections and explain what the data means.

Be ready to answer:
- *"Where does this data come from?"*
- *"What's the difference between this and Langfuse?"*
- *"How long would it take to add a new KPI card?"*

---

## Evaluation Criteria

| Criterion | What assessors look for |
|---|---|
| **Completeness** | All 7 sections present and populated with real data |
| **UI / UX** | Clean layout, readable on a large screen, no clutter |
| **Creativity** | Something beyond the spec — charts, colour coding, auto-refresh |
| **Readability** | A non-technical manager can understand it in 30 seconds |
| **Live deployment** | Working App Runner URL — biggest differentiator |

---

## Bonus (if you finish early)

**Auto-refresh:** Add a refresh button or auto-reload every 30 seconds using `st.rerun()`.
Run the Phase 3 supervisor trigger again — watch your dashboard update automatically.

**Live S3 mode:** Wire the incident report viewer to read the real S3 file.
Add a sidebar toggle so users can switch between demo and live data.

**Mobile view:** Open your App Runner URL on your phone. Fix any layout issues for small screens.

---

## Stuck?

Ask Anil for the reference implementation in `dashboard(stretch)/reference/`.
It is a complete working app — read it, understand it, then make it your own.
Do not copy-paste without understanding. Anil will ask you to explain any line.

---

*Sigma DataTech · Day 12 · Stretch Challenge*
