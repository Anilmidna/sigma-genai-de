# Soda Core Observability Lab: "The Silent Schema Shift"

**Scenario:** You are the Data Engineer responsible for an e-commerce data pipeline. The business requires that all orders have a valid ID, positive amounts, and a known status.
You are using **Soda Core** as your automated observability tool to enforce this Data Contract.

---

### Step 1: Install Soda Core & DuckDB
Soda Core is open-source and extremely lightweight. We will install the DuckDB extension.
Open your terminal and run:
```bash
pip install soda-core-duckdb duckdb
```

### Step 2: Setup the Database
We have provided a script that creates a local DuckDB database. 
It creates two tables:
- `day1_orders`: Perfect, clean data.
- `day2_orders`: Dirty data mimicking a silent upstream failure (negative amounts, missing IDs).

Run the setup script:
```bash
python setup_soda_data.py
```
*You should see a message saying the database is ready.*

### Step 3: Review the Data Contract
Open `checks.yml` in your editor. This is your Service Level Agreement (SLA) written in code!
Instead of writing complex Python, Soda lets you declare rules in simple YAML:
- `duplicate_count(order_id) = 0`
- `min(amount) >= 0`

### Step 4: Run the Baseline (Day 1)
Let's see what happens when the pipeline runs on clean data. We use the Soda CLI to scan the `day1_orders` table.

Run this in your terminal:
```bash
soda scan -d soda_duckdb -c configuration.yml checks.yml
```
**Expected Output:** Everything should be GREEN (Pass). Your data contract is fulfilled!

### Step 5: The Incident (Day 2)
Now, the upstream payment team pushes a broken software update overnight. The pipeline processed the data successfully (no Python crashes!), but the data inside `day2_orders` is corrupted.

Let's point our Soda checks at the dirty data. 
1. Open `checks.yml`
2. Change the first line from `checks for day1_orders:` to `checks for day2_orders:`
3. Save the file.

Now, run the scan again and output the results directly to a JSON file:
```bash
soda scan -d soda_duckdb -c configuration.yml -srf ../output/sodalab_results.json checks.yml
```

### Step 6: Play Detective!
Read the terminal output. You should see a wall of RED failures.
Look at the logs and answer these questions:
1. Which rule caught the negative refund amount?
2. Did Soda catch the missing `customer_id`?
3. If we didn't have Soda running, what would the CEO's dashboard look like tomorrow morning?

**Takeaway:** A pipeline running successfully does NOT mean the data is correct. Soda enforces the contract!

---

### Step 7: Automated Lab Verification
To verify your work and generate the success file for the grading tracker app:

1. Run the verification script:
   ```bash
   python verify_soda.py
   ```
2. If successful, this script checks that your checks are targeting `day2_orders` and have successfully caught the 4 data quality failures. It will output `../output/soda_lab_success.json`.

Your automated tracker app will pick up `../output/soda_lab_success.json` to award your day-end score!
