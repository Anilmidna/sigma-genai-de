import json
import urllib.request
import urllib.error
import sys
import os
import base64

URL_BASE = "http://localhost:8585/api/v1"

def get_token():
    try:
        payload = {
            "email": "admin@open-metadata.org",
            "password": base64.b64encode(b"admin").decode("utf-8")
        }
        url = f"{URL_BASE}/users/login"
        req = urllib.request.Request(url, method="POST")
        req.add_header("Accept", "application/json")
        req.add_header("Content-Type", "application/json")
        json_data = json.dumps(payload).encode("utf-8")
        
        with urllib.request.urlopen(req, data=json_data, timeout=5) as response:
            res = json.loads(response.read().decode('utf-8'))
            return res.get("accessToken")
    except Exception as e:
        print(f"Warning: Failed to obtain authorization token ({e}). Trying request without token.")
        return None

def check_endpoint(endpoint, token=None):
    try:
        url = f"{URL_BASE}/{endpoint}"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception:
        return None
    return None

def main():
    print("Checking OpenMetadata Sandbox installation status...")
    
    # 1. Check server status
    server_up = False
    try:
        urllib.request.urlopen("http://localhost:8585", timeout=5)
        server_up = True
    except Exception:
        pass
        
    if not server_up:
        print("❌ Error: OpenMetadata is not running on http://localhost:8585.")
        print("   Make sure you have started the local Docker sandbox (docker compose up -d) and the server is fully initialized (takes 1-2 mins).")
        sys.exit(1)
        
    print("✓ OpenMetadata Server: RUNNING")
    
    # Obtain token for authorized endpoints
    token = get_token()
    
    # 2. Check Database Services
    db_services = check_endpoint("services/databaseServices", token)
    db_service_count = len(db_services.get("data", [])) if db_services else 0
    print(f"✓ Database Services Configured: {db_service_count}")
    
    # 3. Check Ingested Tables
    tables_data = check_endpoint("tables", token)
    tables_count = len(tables_data.get("data", [])) if tables_data else 0
    print(f"✓ Tables Ingested: {tables_count}")
    
    # 4. Check Data Quality Test Cases
    test_cases_data = check_endpoint("dataQuality/testCases", token)
    test_cases_count = len(test_cases_data.get("data", [])) if test_cases_data else 0
    print(f"✓ Data Quality Test Cases Configured: {test_cases_count}")
    
    # Ensure target output directory exists
    output_dir = "../output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Write output to ../output/openmetadatalab.json
    result = {
        "status": "success",
        "server_running": True,
        "database_services_count": db_service_count,
        "tables_ingested_count": tables_count,
        "data_quality_tests_count": test_cases_count
    }
    
    output_file = os.path.join(output_dir, "openmetadatalab.json")
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
        
    print(f"\n🎉 Verification file '{output_file}' generated successfully!")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
