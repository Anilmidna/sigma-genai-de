# 🩺 Data Therapist: AI-Powered Data Quality Simulator

**Data Therapist** is a complete, interactive, human-in-the-loop data quality simulation tool built for **Sigma DataTech**. The platform demonstrates how modern data pipelines can leverage generative AI for observability, automated SQL/Pandas code prescription, and governance, while exposing a critical engineering trap: **the dangerous downstream side effects of naive AI remediation.**

This project simulates a medallion architecture where messy, raw transactional data (**Bronze**) is diagnosed, treated via a human-approved treatment plan, and promoted to a cleaned analytics table (**Silver**).

---

## 🏗️ Medallion Architecture & System Design

The application consists of five decoupled components that work in tandem:

```
data_therapist/
├── app.py                      # Main Streamlit Dashboard (UI, Plotly charts, state router)
├── requirements.txt            # Python dependencies (Streamlit, DuckDB, Pandas, Boto3, Plotly)
├── db/
│   └── duckdb_manager.py       # DuckDB schema management, dynamic SQL executor, and audit logger
├── llm/
│   ├── diagnosis_engine.py     # Nova Pro calls for structured data quality audits
│   └── remediation_engine.py   # Nova Lite calls for SQL/Pandas fix prescriptions
├── utils/
│   ├── synthetic_data_generator.py # Deterministic random generator for dirty ingestion data
│   └── validators.py           # Downstream business rule auditor and chart generator
```

### Ingestion Flow:
1. **Bronze Layer:** Raw data is generated with realistic transactions containing duplicates, missing customer IDs, spelling variations (`Amazon`, `amazon`, `Amazon Inc`), malformed timestamps, and negative refund amounts.
2. **AI Diagnosis (Round 1):** AWS Bedrock **Nova Pro** scans the footprint of the table, generating a structured audit report detailing issue title, severity, estimated impact, root cause hypotheses, and confidence scores.
3. **AI Prescription (Round 2):** AWS Bedrock **Nova Lite** creates precise, executable DuckDB SQL scripts and equivalent Pandas scripts to fix each issue, accompanied by technical side-effect and downstream risk warnings.
4. **Treatment Plan (Round 3):** An interactive human-in-the-loop dashboard lets data engineers review the SQL and choose to **APPLY**, **REJECT**, or **INVESTIGATE** each fix.
5. **Silver Promotion & Downstream Validation:** The approved DuckDB scripts are executed sequentially. The resulting `silver_transactions` table is promoted, and downstream financial indicators (like Net Revenue and Refund Counts) are computed and visualized.

---

## 🚨 The Central Story: The Negative Amount Trap ("What AI Got Wrong")

A key educational highlight of this application is showing that **a data cleanup routine that achieves a perfect 100% data quality score can still cause a catastrophic business metric failure downstream.**

* **The Anomaly:** Raw Bronze data contains negative transaction amounts (e.g., `-$150.00`) representing legitimate customer **Refunds** and **Chargebacks**.
* **The Naive AI Fix:** The AI model is trained to spot column format errors. It notes that a currency column has negative values and prescribes an absolute value fix:
  ```sql
  UPDATE silver_transactions SET transaction_amount = abs(transaction_amount) WHERE transaction_amount < 0;
  ```
  This fix is technically valid: it makes the data look "clean," resolving all negative currency warnings.
* **The Downstream Disaster:** By removing the negative signs, **refunds are mathematically converted into purchases**. In corporate finance dashboards, this double-counts transactions, artificially inflating Net Revenue (e.g., jumping from a true `$5.09M` to an inflated `$5.12M`) and reducing customer Refund Counts to zero on bookkeeping dashboards.
* **The Safe Human Fix:** A human-in-the-loop rejects the naive absolute value recommendation and instead applies a safe, accounting-aware adjustment:
  ```sql
  UPDATE silver_transactions SET transaction_type = 'REFUND' WHERE transaction_amount < 0;
  ```
  This preserves the negative sign (ensuring accurate net aggregates) while ensuring the transaction type is correctly mapped to finance standards.

---

## ⚡ Prerequisites & Bedrock Integration

The platform operates in two modes:
1. **Mock Mode (Default):** Runs immediately using high-fidelity pre-configured JSON outputs from the LLM. Extremely fast, reliable, and perfect for offline demos, hacking, or interviewing.
2. **Live AWS Bedrock Mode:** Active by toggling "Live AWS Bedrock Mode" in the sidebar. Requires access to Amazon Bedrock models in the `us-east-1` region.

### AWS Credentials Setup
The application utilizes `boto3` to automatically detect your terminal AWS environment. Ensure your terminal has configured credentials:
```bash
aws configure
# Or set environment variables:
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_DEFAULT_REGION="us-east-1"
```
The application calls:
- `amazon.nova-pro-v1:0` for diagnosis.
- `amazon.nova-lite-v1:0` for code remediation.

---

## 🚀 Installation & How to Run

Follow these simple steps to run the application locally:

### 1. Set Workspace (Recommended)
Set this folder as your active IDE workspace to easily manage local terminals:
```bash
cd /Users/as-mac-1291/.gemini/antigravity/scratch/data_therapist
```

### 2. Activate Virtual Environment
We have prepared a dedicated virtual environment with all required libraries:
```bash
source venv/bin/activate
```

### 3. Verify the Backend Pipeline
Before launching the server, run the programmatic backend validation test to ensure schemas, generators, and SQL pipelines function correctly:
```bash
python verify.py
```

### 4. Run the Streamlit Dashboard
Launch the visual user interface in your browser:
```bash
streamlit run app.py
```

The application will launch and open a local server port (typically `http://localhost:8501`).

---

## 📸 Dashboard Preview

### 🏠 Executive Dashboard
*A modern dark dashboard displaying high-level KPIs, Bronze anomaly counts, Silver promotion survival rates, and medallion architecture overview.*

### 🔍 AI Diagnosis Panel
*High-fidelity glassmorphic cards showing detected issues, root cause hypotheses, confidence scores, and business impact audits generated by Nova Pro.*

### 🩺 Human-in-the-loop Treatment Board
*Interactive action controllers for every single data quality issue (Apply / Reject / Investigate), including dynamic code previews and live dynamic pipeline commits.*

### 🚨 DOWNSTREAM OBSERVABILITY SCREEN
*Real-time side-by-side Plotly bar and line comparison charts mapping financial indicators across Bronze Raw, Naive AI Promoted, and Human-Governed Promoted Silver tables, detailing the revenue inflation.*
