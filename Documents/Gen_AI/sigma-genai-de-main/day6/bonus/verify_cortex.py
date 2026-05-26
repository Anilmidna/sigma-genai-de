"""Verify Cortex access works. Run: python verify_cortex.py"""
import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import snowflake.connector

key_path = os.path.join(os.path.dirname(__file__), 'student_key.p8')

if not os.path.exists(key_path):
    print("ERROR: student_key.p8 not found in this folder.")
    print("Download it from Slack and place it here.")
    exit(1)

with open(key_path, 'rb') as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

private_key_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

print("Connecting to Snowflake...")
conn = snowflake.connector.connect(
    user='student_genai',
    account='GEJKIOG-TKC55632',
    private_key=private_key_bytes,
    database='SIGMA_DE',
    schema='PUBLIC',
    warehouse='COMPUTE_WH',
    role='STUDENT_CORTEX'
)
cur = conn.cursor()

print("Testing Cortex AI...")
cur.execute("SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-7b', 'Say OK')")
print(f"  Cortex response: {cur.fetchone()[0].strip()}")

print("Testing data access...")
cur.execute("SELECT COUNT(*) FROM FACT_TRANSACTIONS")
print(f"  Row count: {cur.fetchone()[0]}")

conn.close()
print("\nAll good! Cortex + data access verified.")
