# Write Your Pipeline Spec — Before You Touch Any Code

## Instructions to Students

- Your team has been assigned one scenario below (by table number)
- Fill in the spec template at the bottom of this file
- You have **30 minutes** — use the full time
- Your spec must answer all 6 sections
- After 30 minutes: trainer cold-calls one person from each team to read their spec aloud (2 minutes each)
- **THEN** you run Module 1 on YOUR spec (not the sample one)
- Each team's pipeline output will be different — your output files prove YOUR team ran it

---

## The 8 Team Scenarios

### Team 1 — Customer Churn Prediction Feed

Sigma DataTech wants to identify customers at risk of churning before they leave. Build a daily pipeline that reads transaction history, calculates recency/frequency/monetary (RFM) features per customer, flags customers with no transaction in 14 days as `at_risk`, and writes a `churn_risk` table to the Gold layer.

---

### Team 2 — Merchant Fraud Detection Feed

The risk team suspects some merchants have unusually high failure rates. Build a pipeline that reads daily transactions, calculates `failure_rate` per merchant per day, flags merchants where `failure_rate > 30%` as `suspicious`, and writes a `merchant_risk_scores` table with a `confidence_level` column.

---

### Team 3 — Marketing Attribution Pipeline

Sigma DataTech runs promotions via 3 channels: Email, SMS, Push. Build a pipeline that reads transaction data + a promotions CSV (`promo_id`, `channel`, `discount_pct`), joins them on `customer_id`, calculates `revenue_per_channel` and `roi_per_channel`, and writes a `marketing_attribution` Gold table.

---

### Team 4 — Customer Segmentation Refresh

The CRM team needs customers grouped by spend behaviour. Build a pipeline that reads 30 days of transaction history, calculates `total_spent` and `txn_frequency` per customer, segments into 4 tiers: VIP (>5000), High (1000–5000), Mid (200–1000), Low (<200), and writes a `customer_segments` table with `segment_updated_date`.

---

### Team 5 — Regulatory Compliance Report

Finance needs a daily audit trail for RBI compliance. Build a pipeline that reads ALL transactions (not just COMPLETED), adds a `compliance_flag` column (flag any transaction > 50000 as `requires_review`), calculates daily totals by `payment_method`, and writes a `compliance_daily_summary` table with a `report_generated_at` timestamp.

---

### Team 6 — Partner Data Feed

Sigma DataTech shares a daily performance summary with 3 merchant partners. Build a pipeline that reads Gold `merchant_performance` data, filters to only that partner's `merchant_id`s, masks `customer_id` (replace with a hash), and writes a `partner_feed_{partner_id}.parquet` file per partner.

---

### Team 7 — Real-Time Pricing Intelligence

The product team wants to adjust transaction fee rates based on volume. Build a pipeline that reads yesterday's transactions, calculates `txn_volume_by_payment_method`, applies a fee rate lookup (Credit: 2%, Debit: 1.5%, UPI: 0%), calculates `effective_revenue` after fees, and writes a `fee_analysis` Gold table.

---

### Team 8 — Data Quality Scorecard

The data governance team wants a daily health report. Build a pipeline that reads Silver transactions, calculates: `null_rate` per column, `duplicate_rate`, `schema_match` (1 if all expected columns present else 0), and an `overall_quality_score` (0–100), and writes a `data_quality_scorecard` table with `run_date`.

---

### Team 9 — Transaction Reconciliation Pipeline

Sigma DataTech processes payments through 3 gateways: Razorpay, PayU, and Stripe. Each gateway sends a daily settlement file with their record of transactions. Build a pipeline that reads Sigma's internal transaction ledger AND each gateway's settlement file, matches records on `transaction_id`, classifies each as `matched` (both sides agree on amount), `disputed` (amount difference > ₹1), or `missing` (in ledger but absent from gateway file), calculates `net_variance` per gateway, and writes a `reconciliation_summary` table with `reconciliation_date`. The finance team uses this to flag gateways for manual review before end-of-day settlement.

---

## Spec Template

Refer to Google Drive - Day 7 - Day7_Spec_Review.xlsx - Fill this as a Team - 

**TIME LIMIT - 15 MINS**
```

**Use Template in Google Drive to fill and submit:** You will be asked a tricky question on the Spec and be prepared for that !!!!! :-()


Note : When you do the next Lab - Module 1 (`1_spec_to_pipeline.py`) will automatically detect that file and use YOUR spec instead of the sample. Your `pipeline_brain/generated_pipeline.py` will be unique to your team's scenario.
