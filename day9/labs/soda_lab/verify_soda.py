import json
import os
import sys

RESULTS_FILE = "../output/sodalab_results.json"
CHECKS_FILE = "checks.yml"

def main():
    print("Checking Soda Core Lab completion status...")
    
    # 1. Check if sodalab_results.json was generated
    if not os.path.exists(RESULTS_FILE):
        print(f"❌ Error: {RESULTS_FILE} not found. Run the scan with the '-srf' option:")
        print("   soda scan -d soda_duckdb -c configuration.yml -srf ../output/sodalab_results.json checks.yml")
        sys.exit(1)
        
    # 2. Parse the results file
    try:
        with open(RESULTS_FILE, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error: Failed to parse {RESULTS_FILE} as JSON: {e}")
        sys.exit(1)
        
    # 3. Check if they scanned day2_orders
    checks = data.get("checks", [])
    if not checks:
        print("❌ Error: No checks found in the results file. Make sure your checks.yml is configured correctly.")
        sys.exit(1)
        
    scanned_day2 = False
    failures = 0
    passes = 0
    for check in checks:
        definition = check.get("definition", "")
        table_name = check.get("table", "")
        if "day2_orders" in table_name or "day2_orders" in definition:
            scanned_day2 = True
        outcome = check.get("outcome", "")
        if outcome == "fail":
            failures += 1
        elif outcome == "pass":
            passes += 1
            
    if not scanned_day2:
        # Check if the checks.yml file has "day2_orders"
        with open(CHECKS_FILE, "r") as f:
            content = f.read()
        if "day2_orders" in content:
            scanned_day2 = True
            
    if not scanned_day2:
        print("❌ Error: Your checks.yml is still pointing to 'day1_orders'.")
        print("   Please edit checks.yml, change the first line to 'checks for day2_orders:', and run the scan again.")
        sys.exit(1)
        
    print("✓ Checks targeting 'day2_orders': YES")
    print(f"✓ Detected failures: {failures} (Expected: 4)")
    print(f"✓ Detected passes: {passes} (Expected: 2)")
    
    if failures >= 4:
        print("🎉 Verification SUCCESS! All data quality violations successfully detected.")
        result = {
            "status": "success",
            "scanned_table": "day2_orders",
            "failures_detected": failures,
            "passes_detected": passes,
            "soda_observability_verified": True
        }
        
        # Ensure target output directory exists
        output_dir = "../output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        # Save validation file for the tracker app
        output_file = os.path.join(output_dir, "soda_lab_success.json")
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"✓ Created '{output_file}' for the tracker app.")
    else:
        print(f"❌ Error: Found only {failures} failures. Expected at least 4. Ensure you haven't altered setup_soda_data.py.")
        sys.exit(1)

if __name__ == "__main__":
    main()
