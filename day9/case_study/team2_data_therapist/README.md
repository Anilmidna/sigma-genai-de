# 🩺 Data Therapist — AI-Powered Data Quality Remediation Simulator

> **Sigma DataTech AI Ops Platform | Day 9 | Team 2**

---

## Project Overview

**Data Therapist** is a Streamlit application that simulates an enterprise AI-powered data quality remediation workflow. It demonstrates how AI can diagnose bad data, prescribe fixes, and warn about risks — while keeping humans in control of every remediation decision before data is promoted from Bronze to Silver.

### The Core Business Problem
Sigma DataTech's data team spends **3 hours every morning** manually investigating data quality issues in the Bronze layer. Data Therapist automates diagnosis and prescription — but proves why human approval is non-negotiable.

---

## Architecture

```
team2_data_therapist/
├── app.py                          # Main Streamlit application (7-page navigation)
├── requirements.txt
├── README.md
│
├── utils/
│   ├── synthetic_data_generator.py  # Generates dirty Bronze transaction data
│   └── validators.py                # Downstream validation checks
│
├── db/
│   └── duckdb_manager.py           # DuckDB Bronze/Silver operations
│
├── llm/
│   ├── diagnosis_engine.py          # Round 1: Nova Pro diagnosis
│   └── remediation_engine.py        # Round 2: Nova Lite prescription
│
└── data/                            # Auto-created: therapist.duckdb
```

### Technology Stack
| Component | Technology |
|---|---|
| UI Framework | Streamlit |
| Database | DuckDB (in-memory + file) |
| AI — Diagnosis | Amazon Nova Pro |
| AI — Prescription | Amazon Nova Lite |
| Data Processing | Pandas |
| Visualization | Plotly |
| AWS Integration | Boto3 |

---

## Setup & Installation

### Prerequisites
- Python 3.9+
- AWS CLI configured with credentials that have access to Amazon Bedrock (us-east-1)
- Bedrock model access enabled for: `amazon.nova-pro-v1:0` and `amazon.nova-lite-v1:0`

### Installation

```bash
cd day9/team2_data_therapist

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Running the App

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

> **Note:** If AWS Bedrock credentials are not available, the app will automatically fall back to realistic mocked AI responses. No credentials are required to run the demo.

---

## Demo Flow

Follow this sequence for the best live demo experience:

1. **🏠 Home** — Review the architecture and workflow overview
2. **🥉 Bronze Data** — Click "Generate & Load Bronze Data" to create the dirty dataset
3. **🤖 AI Diagnosis** — Click "Run Nova Pro Diagnosis" to get AI-powered issue analysis
4. **💊 AI Prescription** — Click "Run Nova Lite Prescription" to generate fix recommendations
5. **📋 Treatment Plan** — Review each fix and decide: APPLY / REJECT / INVESTIGATE
6. **🥈 Silver Validation** — See downstream metrics and before/after comparison
7. **⚠️ What AI Got Wrong** — Understand why the dangerous fix was wrong

---

## The Dangerous AI Fix (Key Learning Objective)

### The Trap: DX003 — "Convert Negative Amounts to Positive"

**What Nova Lite recommended:**
```sql
UPDATE bronze_transactions
SET transaction_amount = ABS(transaction_amount)
WHERE transaction_amount < 0;
```

**Why it looked correct:**
- Reduces negative amount violations from 6 to 0
- Data quality score improves from 71% to 94%
- All validation checks pass
- Dashboard shows green

**Why it was catastrophically wrong:**
- REFUND transactions (e.g., `-₹500`) are legitimately negative — that's how Sigma DataTech records them
- ABS() converts `-₹500 REFUND` → `+₹500 PURCHASE`
- Revenue inflates by ~15-20%
- Finance dashboard shows incorrect GMV
- Monthly refund report shows ₹0 in refunds
- Chargeback risk model loses its negative signal entirely

**The correct fix:**
```sql
-- Only convert non-refund negatives (data entry errors)
UPDATE bronze_transactions
SET transaction_amount = ABS(transaction_amount)
WHERE transaction_amount < 0
  AND transaction_type != 'REFUND';
```

**Why human oversight mattered:**
The prescription's own side-effect warning explicitly stated the risk: *"This fix will ALSO convert legitimate REFUND transactions to positive values."* A human who reads this carefully will reject the fix. An automated pipeline would apply it without question.

---

## Data Quality Issues Injected

| Issue ID | Issue | Severity | Fix Strategy |
|---|---|---|---|
| DX001 | Duplicate Transaction IDs | HIGH | Deduplicate by latest timestamp |
| DX002 | Null Merchant Names | MEDIUM | Fill with UNKNOWN |
| DX003 | Negative Amounts (Non-Refund) | HIGH | **⚠️ DANGEROUS — ABS() corrupts refunds** |
| DX004 | Malformed Timestamps | HIGH | Remove impossible dates |
| DX005 | Missing Customer IDs | MEDIUM | Fill with UNKNOWN_CUST |
| DX006 | Invalid Transaction Types | MEDIUM | Recode to UNKNOWN |
| DX007 | Outlier Amounts (>₹1L) | HIGH | Route to review queue |
| DX008 | Whitespace in Merchant Names | LOW | TRIM() — safe |
| DX009 | Invalid Source System Codes | MEDIUM | Filter to known systems |
| DX010 | Null Transaction IDs | HIGH | Remove unresolvable rows |

---

## Key Themes Demonstrated

- ✅ **Human-in-the-Loop AI** — Every fix requires explicit human approval
- ✅ **Data Quality Governance** — Audit trail for all decisions (APPLY/REJECT/INVESTIGATE)
- ✅ **Root Cause Analysis** — AI explains *why* an issue happened, not just that it exists
- ✅ **Downstream Impact Validation** — Silver metrics reveal hidden AI fix damage
- ✅ **Safe AI Remediation** — Side-effect warnings are mandatory, not optional
- ✅ **Bronze/Silver Medallion Architecture** — Traceability from raw to clean
- ✅ **AI Observability** — Confidence scores, affected row estimates, fix lineage

---

## Screenshots

> *(Add screenshots from your live demo here)*

- `screenshots/01_bronze_data.png` — Bronze layer health dashboard
- `screenshots/02_ai_diagnosis.png` — Nova Pro diagnosis results
- `screenshots/03_prescription_dangerous.png` — The dangerous prescription warning
- `screenshots/04_treatment_plan.png` — Human review workflow
- `screenshots/05_silver_validation.png` — Before/after downstream metrics
- `screenshots/06_what_ai_got_wrong.png` — Post-mortem analysis

---

## Team 2 — Pitch Checklist

- [ ] Live demo: Diagnosis → Prescription → Treatment
- [ ] Show the dangerous fix (DX003) and why it was rejected
- [ ] Show Silver row survival percentage
- [ ] Explain what "healthy data" looks like for Sigma DataTech
- [ ] Reveal the downstream metric that broke when AI got it wrong
