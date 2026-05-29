import urllib.request
import urllib.error
import json
import base64

URL_BASE = "http://localhost:8585/api/v1"

def get_token():
    payload = {
        "email": "admin@open-metadata.org",
        "password": base64.b64encode(b"admin").decode("utf-8")
    }
    url = f"{URL_BASE}/users/login"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    json_data = json.dumps(payload).encode("utf-8")
    
    with urllib.request.urlopen(req, data=json_data) as response:
        res = json.loads(response.read().decode('utf-8'))
        return res["accessToken"]

def send_put(endpoint, token, data):
    url = f"{URL_BASE}/{endpoint}"
    req = urllib.request.Request(url, method="PUT")
    req.add_header("Accept", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    json_data = json.dumps(data).encode("utf-8")
    
    try:
        with urllib.request.urlopen(req, data=json_data, timeout=10) as response:
            if response.status in (200, 201):
                res = json.loads(response.read().decode('utf-8'))
                print(f"✓ PUT {endpoint} SUCCESS: {res.get('fullyQualifiedName', res.get('name'))}")
                return res
            else:
                print(f"✗ PUT {endpoint} ERROR status {response.status}: {response.read().decode('utf-8')}")
    except urllib.error.HTTPError as e:
        print(f"✗ PUT {endpoint} HTTP Error {e.code}: {e.reason}")
        try:
            print(e.read().decode('utf-8'))
        except Exception:
            pass
    except Exception as e:
        print(f"✗ PUT {endpoint} Error: {e}")
    return None

def main():
    token = get_token()
    print("Logged in successfully!")
    
    # 1. Create Database Service
    db_service_payload = {
        "name": "local_mysql",
        "displayName": "Local MySQL Database",
        "serviceType": "Mysql",
        "connection": {
            "config": {
                "type": "Mysql",
                "hostPort": "openmetadata_mysql:3306",
                "username": "openmetadata_user",
                "authType": {
                    "password": "openmetadata_key"
                }
            }
        }
    }
    db_service = send_put("services/databaseServices", token, db_service_payload)
    if not db_service:
        print("Failed to create database service. Exiting.")
        return
        
    # 2. Create Database
    db_payload = {
        "name": "sales_db",
        "displayName": "Sales DB",
        "service": "local_mysql"
    }
    db = send_put("databases", token, db_payload)
    if not db:
        print("Failed to create database. Exiting.")
        return

    # 3. Create Database Schema
    schema_payload = {
        "name": "sales_schema",
        "displayName": "Sales Schema",
        "database": "local_mysql.sales_db"
    }
    schema = send_put("databaseSchemas", token, schema_payload)
    if not schema:
        print("Failed to create database schema. Exiting.")
        return

    # 4. Create Table
    table_payload = {
        "name": "customers",
        "displayName": "Customers Table",
        "databaseSchema": "local_mysql.sales_db.sales_schema",
        "columns": [
            {
                "name": "customer_id",
                "dataType": "INT",
                "dataTypeDisplay": "int",
                "description": "Primary key customer ID"
            },
            {
                "name": "email",
                "dataType": "VARCHAR",
                "dataLength": 255,
                "dataTypeDisplay": "varchar(255)",
                "description": "Customer email address"
            }
        ]
    }
    table = send_put("tables", token, table_payload)
    if not table:
        print("Failed to create table. Exiting.")
        return

    # 5. Create Test Case (without testSuite)
    test_case_payload = {
        "name": "email_not_null",
        "testDefinition": "columnValuesToBeNotNull",
        "entityLink": "<#E::table::local_mysql.sales_db.sales_schema.customers::columns::email>",
        "parameterValues": [],
        "description": "Ensure email addresses are not null"
    }
    test_case = send_put("dataQuality/testCases", token, test_case_payload)
    if not test_case:
        print("Failed to create test case. Exiting.")
        return

    print(f"Test Case Created: {test_case['id']}")
    print("\n🎉 OpenMetadata resources successfully populated!")

if __name__ == "__main__":
    main()
