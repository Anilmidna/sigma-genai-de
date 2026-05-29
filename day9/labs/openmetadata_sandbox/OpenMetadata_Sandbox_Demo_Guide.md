# OpenMetadata Sandbox Demo – Beginner Step-by-Step Guide

Welcome to the OpenMetadata Sandbox Demo Guide! This document is designed for beginners and freshers who want to understand the fundamentals of metadata management, data discovery, and data governance.

## 🌟 What is OpenMetadata?

**OpenMetadata** is an open-source metadata management and data governance platform. In simple terms, think of it as:
> **"Google Maps + LinkedIn + Wikipedia for your company's Data Assets."**

It answers questions like:
- Where is my data? (Discovery)
- How did it get here? (Lineage)
- Can I trust it? (Data Quality)
- Who is responsible for it? (Ownership)
- What does this column mean? (Glossary & Tags)

> [!IMPORTANT]
> **Key Concept for Beginners:** OpenMetadata stores **Metadata** (data about data, such as schema names, column types, and descriptions), **NOT the actual raw data** (no customer PII rows, no financial transactions). This ensures data security and compliance.

---

## 🌍 The Big Picture: Why Industry Needs Metadata Management

In modern enterprises, data is stored across dozens of scattered systems (databases, data lakes, BI dashboards, Kafka streams). Without a central directory, companies face major operational friction:
*   **Data Silos & Discovery Issues:** Developers and analysts spend up to **30-40% of their time just trying to find** where a specific dataset exists and who owns it.
*   **Lack of Trust (Bad Data Quality):** Reports are generated from stale, duplicate, or broken tables, leading to incorrect business decisions.
*   **High Debugging Time:** When a pipeline breaks, data engineers spend hours tracing code back to find the root cause.
*   **Governance & Compliance Audits:** Under regulations like GDPR, HIPAA, or CCPA, companies must know exactly where sensitive data (like emails or credit cards) is stored and who has access to it.

**The Solution:** OpenMetadata acts as a **unified control plane** that automates metadata collection, provides visual lineage, monitors data quality, and enforces governance policies across the entire data stack in one place.

---

## ⚔️ Competitors & Similar Tools

When companies look for data cataloging and governance tools, they evaluate several alternatives:

| Category | Tool | How it Compares to OpenMetadata |
| :--- | :--- | :--- |
| **Open-Source** | **Acryl DataHub** | Originally built at LinkedIn. It is OpenMetadata's main open-source rival. It is highly push-based and scalable but can be more complex to set up and host. |
| **Open-Source** | **Amundsen** | Created by Lyft. Great for simple data discovery and search, but lacks the built-in data quality testing and advanced governance features of OpenMetadata. |
| **Enterprise / Proprietary** | **Alation** | A pioneer in the data catalog space. Extremely rich enterprise features and great user experience, but it is proprietary, very expensive, and closed-source. |
| **Enterprise / Proprietary** | **Collibra** | The industry standard for heavy corporate data governance and compliance. Great for large institutions but has a steep learning curve and high license costs. |
| **Cloud Native** | **AWS Glue Catalog / GCP Dataplex** | Cloud-managed catalogs. They work perfectly within their respective cloud ecosystems (AWS/GCP) but do not offer the rich cross-platform UI, lineage, and collaboration features of OpenMetadata. |

---

## 🎯 Demo Goals

In this 20-minute walk-through, you will learn how to:
1. Log in to the OpenMetadata Sandbox
2. Navigate the central dashboard
3. Understand Service Connections & Ingestion
4. Browse tables and metadata details
5. Visualize end-to-end Data Lineage
6. Classify data with Tags & Glossary Terms
7. Monitor Data Quality & Test Suites
8. Use search filters effectively
9. Understand real-world enterprise scenarios

---

## 🚀 Step 1 — Access the Sandbox

There are two ways to explore OpenMetadata:

> [!IMPORTANT]
> **Grading / Tracker Requirement:** You **MUST use Option B (Local Docker Sandbox)** to complete the lab and generate the success file for the grading tracker. The Public Sandbox (Option A) is read-only and does not allow you to run ingestions or create test cases, which will cause the verification script to fail.

### Option A: The Public Sandbox (Easiest & Read-Only)
Google hosts a shared sandbox loaded with rich mock data from standard enterprises.
*   **URL:** [sandbox.open-metadata.org](https://sandbox.open-metadata.org)
*   **Login:** Click "Sign in with Google" (use any Google account).
*   > [!NOTE]
    > In the public sandbox, you can explore everything but cannot create new database service connections or run ingestion (Steps 3 & 4) because write permissions are restricted.

### Option B: Local Docker Sandbox (Full Admin Access)
If you want to connect to a local database and ingest metadata yourself, navigate to this lab directory and start the Docker services (we have pre-downloaded the official `docker-compose.yml` file here for you!):
```bash
cd repo/day9/labs/openmetadata_sandbox
docker compose up -d
```
*   **Default URL:** `http://localhost:8585`
*   **Default Login:** Username: `admin` / Password: `admin`

---

## 🔍 Step 2 — Explore the Home Dashboard

Once logged in, take a look around the home screen:

- **Activity Feed:** See who added a description, created a glossary term, or if a data quality test failed.
- **My Data:** Shows assets you own or frequently use.
- **Top Tables / Popular Dashboards:** Shows the most viewed assets in your organization.
- **Data Domains:** Logical groupings of data (e.g., Finance, Marketing, Operations).

> [!TIP]
> **For Beginners:** The dashboard is the "Data Portal homepage" for data analysts, data engineers, and data scientists when they start their workday.

---

## 🔌 Step 3 — Create a Database Service Connection

> [!NOTE]
> *If you are using the public sandbox, skip to Step 5 as service creation is disabled. Observe the existing services instead.*

To bring metadata into OpenMetadata, you first define a **Service**.

1. Go to: **Settings** (Gear icon on the left menu) → **Services** → **Databases**
2. Click **Add New Service**.
3. Choose your database type (e.g., `MySQL`, `PostgreSQL`, `Snowflake`, `BigQuery`).
4. Enter the connection details:
   - **Host & Port:** Database address.
   - **Credentials:** Username and Password.
   - **Database Name:** The target database.
5. Click **Test Connection** (checks if OpenMetadata can reach your database) and then click **Save**.

> [!TIP]
> **Why do we do this?** OpenMetadata doesn't read your files directly; it connects to your databases and tools via these service definitions to scan their catalogs.

---

## ⚙️ Step 4 — Run Metadata Ingestion

After creating the service connection, you must set up an **Ingestion Pipeline**.

1. Click **Add Metadata Ingestion** immediately after saving your service.
2. Configure the schedule (e.g., hourly, daily, or run manually).
3. Click **Deploy**.
4. The pipeline connects to your database, queries the system catalog (information schema), and extracts:
   - Tables and Views
   - Schema structural details
   - Columns and Column data types (VARCHAR, INT, etc.)

> [!IMPORTANT]
> **How Ingestion Works:** OpenMetadata uses a lightweight Python-based ingestion framework. It runs queries like `SHOW TABLES` on your database, bundles that structure into JSON metadata, and sends it to the OpenMetadata server via REST APIs.

---

## 📊 Step 5 — Explore Tables & Data Assets

Go to the search bar or navigate to **Explore** → **Tables** and open a sample table (e.g., `raw_customer`).

Explore the tabs available for every table:
- **Schema:** Shows column names, types, descriptions, and tags.
- **Profiler & Data Quality:** Visual graphs showing null rates, distribution, and test results.
- **Lineage:** Visual diagram showing data flows.
- **Sample Data:** A safe, limited preview of table rows (if configured).
- **Queries:** Frequently run SQL queries against this table (helps freshers learn how to query it!).

---

## 🌿 Step 6 — View Data Lineage

Open a table, and click on the **Lineage** tab.

You will see a visual map of nodes and arrows:
`Source Table (e.g., raw_users) ➔ Airflow/dbt transformation ➔ Target Table (e.g., dim_users) ➔ BI Dashboard (e.g., User Growth Report)`

> [!TIP]
> **Why Lineage is a Lifesaver:**
> Imagine a manager says, *"The Sales Dashboard is showing wrong numbers!"* Without lineage, you'd spend hours searching through code. With lineage, you click on the dashboard node, look backward to see which table feeds it, and check which step of the pipeline failed. This is called **Impact Analysis**.

---

## 🏷️ Step 7 — Add Tags & Classifications

Go to any table column (like `email` or `credit_card`) and click **Add Tag**.

- Tag it as **PII (Personally Identifiable Information)** or **Sensitive**.
- Tag the table as **Gold Layer** (clean production data) or **Bronze Layer** (raw data).

> [!NOTE]
> **Tags** are technical labels used for categorization, access control, and compliance. For example, security teams can create a policy: *"If a column is tagged as PII.Sensitive, hide it from junior developers."*

---

## 📖 Step 8 — Create and Assign Glossary Terms

Go to the **Glossary** section on the left sidebar.

1. Observe terms like `Active Customer`, `Monthly Recurring Revenue (MRR)`, or `Churn Rate`.
2. Notice how they have clear business descriptions.
3. Link a glossary term to a table column (e.g., link the glossary term `MRR` to the column `monthly_subscription_amount`).

> [!TIP]
> **Glossary vs. Tags (A Common Interview Question!):**
> *   **Glossary Terms** represent business definitions. They help ensure that a business analyst and a data engineer mean the exact same thing when they say "Active User."
> *   **Tags** are technical classifications used for compliance, lifecycle, or tiering (e.g., `PII`, `GDPR`, `Tier_1`).

---

## 🧪 Step 9 — Monitor Data Quality

Go to **Data Quality** in the sidebar.

Observe the test cases:
*   `column_values_to_be_not_null` (e.g., checking that `customer_id` is never blank).
*   `column_values_to_be_unique` (e.g., checking that `email` has no duplicates).
*   `column_value_lengths_to_be_between` (e.g., checking that `phone_number` is valid).

> [!NOTE]
> OpenMetadata allows you to write these tests directly from the UI without writing code. If a test fails, OpenMetadata can send an alert to Slack, Microsoft Teams, or email immediately.

---

## 🔍 Step 10 — Leverage the Search Feature

Use the global search bar at the very top (just like searching on Google).

1. Search for: `sales` or `customer`.
2. Use the left-side filters to narrow search results by:
   - **Service Type** (e.g., show only BigQuery tables)
   - **Tier** (e.g., show only Tier-1 business-critical tables)
   - **Owner** (e.g., show tables owned by the "Finance Team")
   - **Tag** (e.g., show only tables with "PII")

---

## 🏢 Real-World Demo Story

To help freshers understand the value, explain this scenario:

*   **The Problem:** At *AnyCompany Corp*, a data engineer leaves the company. The marketing team wants to run a campaign using the `customer_leads` table, but they don't know:
    1. Who owns this table now?
    2. Is this table fresh, or is it outdated?
    3. Are the email addresses in it validated, or are there nulls?
    4. Which ETL job updates it?
*   **The Solution:** They search for `customer_leads` in OpenMetadata. Within 2 minutes, they see:
    - It is owned by the **Growth Team**.
    - It passed all **Data Quality tests** this morning.
    - The lineage shows it is updated by an Airflow DAG named `daily_leads_sync`.
    - Column descriptions explain what each field represents.

---

## ✅ Step 11 — Automated Lab Verification

If you are using the **Local Docker Sandbox**, your completion status can be automatically verified.

### Verification Steps
To verify your work and generate the grading file for the submission tracker, run the following commands in your terminal:

1. Navigate to the OpenMetadata lab directory:
   ```bash
   cd repo/day9/labs/openmetadata_sandbox
   ```
2. Run the verification script:
   ```bash
   python verify_openmetadata.py
   ```

### What This Script Checks:
*   **Server Status:** Is OpenMetadata running locally on `http://localhost:8585`?
*   **Database Services:** Have you successfully created at least one Database Service?
*   **Ingested Tables:** Have you run metadata ingestion to import tables?
*   **Data Quality Tests:** Have you set up at least one test case on your tables?

### Verification File Output
This script queries the OpenMetadata REST APIs directly and outputs the results to `../output/openmetadatalab.json`. The automated tracker app will pick up this file to mark your task as **Success**.

Example output file content (`../output/openmetadatalab.json`):
```json
{
  "status": "success",
  "server_running": true,
  "database_services_count": 1,
  "tables_ingested_count": 8,
  "data_quality_tests_count": 3
}
```

> [!WARNING]
> Ensure your local OpenMetadata container is active (`docker compose up -d`) and you have fully completed the database ingestion and test creation steps before running the verification script, or the count values will register as `0` and fail the tracker check.

---

## ⏱️ Suggested 20-Minute Demo Agenda

If you are presenting this demo to a class or team:

| Duration | Topic | Key Focus |
| :--- | :--- | :--- |
| **2 Mins** | Introduction | Explain what metadata is and the Google Maps analogy. |
| **3 Mins** | Explore UI | Home page, search bar, activity feed. |
| **4 Mins** | Connect & Ingest | Service connections and how python-based metadata ingestion works. |
| **3 Mins** | Table Inspection | Columns, descriptions, queries, and sample data. |
| **3 Mins** | Lineage & Quality | Visualizing data flow and automated test suites. |
| **3 Mins** | Governance | Adding Tags (PII) and Glossary Terms (business meaning). |
| **2 Mins** | Q&A | Answering questions about real-world use cases. |

---

## 🎓 Key Takeaways for Freshers

1. **Collaboration is Key:** OpenMetadata is collaborative—anyone can suggest descriptions, ask questions, or assign tasks.
2. **Observability Matters:** Knowing a pipeline failed is good, but knowing *which datasets and dashboards are affected* (via Lineage) is critical.
3. **Career Relevance:** Modern data teams are moving from chaotic data lakes to governed **Data Meshes**. Knowing metadata tools like OpenMetadata is a highly sought-after skill in DataOps, Data Engineering, and Data Governance.
