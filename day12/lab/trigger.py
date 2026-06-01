"""
==============================================================================
SIGMA INTELLIGENCE PLATFORM — PIPELINE TRIGGER
Run this from YOUR LAPTOP to trigger the agents running on EC2.
==============================================================================
Usage:
  python lab/trigger.py --ec2-ip 54.123.45.67 --bucket sigma-datatech-team1

  # Watch live status while pipeline runs:
  python lab/trigger.py --ec2-ip 54.123.45.67 --bucket sigma-datatech-team1 --watch

  # Check health of all services:
  python lab/trigger.py --ec2-ip 54.123.45.67 --health-check
==============================================================================
"""

import argparse, json, sys, time
from datetime import datetime

try:
    import requests
except ImportError:
    print("[ERROR] pip install requests")
    sys.exit(1)

def print_separator(char="=", width=60):
    print(char * width)

def health_check(ec2_ip: str, timeout: int = 5):
    """Check health of all 5 services on EC2."""
    services = {
        "Supervisor":    f"http://{ec2_ip}:8001/health",
        "Schema Agent":  f"http://{ec2_ip}:8002/health",
        "PII Agent":     f"http://{ec2_ip}:8003/health",
        "Quality Agent": f"http://{ec2_ip}:8004/health",
        "MCP Server":    f"http://{ec2_ip}:8005/health",
    }
    print_separator()
    print(f"HEALTH CHECK — EC2: {ec2_ip}")
    print_separator()
    all_ok = True
    for name, url in services.items():
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                print(f"  ✓ {name:20} OK  | {url}")
                if name == "MCP Server":
                    tools = data.get("tools", 0)
                    mem   = data.get("memory", {})
                    print(f"    Tools available: {tools}")
                    if isinstance(mem, dict) and "collections" in mem:
                        for col, cnt in mem["collections"].items():
                            print(f"    Memory [{col}]: {cnt} documents")
            else:
                print(f"  ✗ {name:20} HTTP {resp.status_code} | {url}")
                all_ok = False
        except requests.exceptions.ConnectionError:
            print(f"  ✗ {name:20} NOT REACHABLE | {url}")
            print(f"    Check: sudo systemctl status sigma-{name.lower().replace(' ','-')}")
            all_ok = False
        except Exception as e:
            print(f"  ✗ {name:20} ERROR: {e}")
            all_ok = False

    print_separator()
    if all_ok:
        print("  ALL SERVICES HEALTHY — ready to trigger pipeline")
    else:
        print("  SOME SERVICES DOWN — fix before running pipeline")
        print("  SSH to EC2 and check: journalctl -u sigma-supervisor -f")
    print_separator()
    return all_ok

def trigger_pipeline(ec2_ip: str, bucket: str, prefix: str, watch: bool):
    """Send pipeline trigger to supervisor on EC2."""
    supervisor_url = f"http://{ec2_ip}:8001/trigger"
    payload = {"bucket": bucket, "prefix": prefix, "mode": "full"}

    print_separator()
    print("SIGMA INTELLIGENCE PLATFORM — PIPELINE TRIGGER")
    print_separator()
    print(f"  EC2 Supervisor : {supervisor_url}")
    print(f"  S3 Bucket      : {bucket}")
    print(f"  S3 Prefix      : {prefix}")
    print(f"  Triggered at   : {datetime.now().strftime('%H:%M:%S')}")
    print_separator()
    print()
    print("  Sending trigger to supervisor...")
    print("  Watch EC2 logs: journalctl -u sigma-* -f")
    print()

    try:
        start = time.time()
        resp  = requests.post(supervisor_url, json=payload, timeout=180)
        elapsed = round(time.time() - start, 1)

        if resp.status_code != 200:
            print(f"  [ERROR] Supervisor returned HTTP {resp.status_code}")
            print(f"  Response: {resp.text[:500]}")
            return

        result = resp.json()

        print_separator()
        print("PIPELINE COMPLETE")
        print_separator()
        print(f"  Run ID          : {result.get('run_id','?')}")
        print(f"  Duration        : {result.get('duration_sec','?')}s")
        print(f"  File processed  : {result.get('file_processed','?')}")
        print(f"  Agents called   : {result.get('agents_called','?')}")
        print()

        # Schema Agent result
        schema = result.get("schema_result", {})
        drift  = schema.get("drift_detected", False)
        print(f"  SCHEMA AGENT    : {'DRIFT DETECTED' if drift else 'No drift'}")
        if drift:
            dd = schema.get("drift_details", {})
            print(f"    Added   : {dd.get('added', [])}")
            print(f"    Renamed : {dd.get('renamed', {})}")
            rem = schema.get("remediation", {})
            print(f"    Action  : {rem.get('recommended_action','?')}")

        # PII Agent result
        pii   = result.get("pii_result", {})
        n_pii = pii.get("pii_columns_found", 0)
        tier  = pii.get("dataset_sensitivity", "?")
        print(f"\n  PII AGENT       : {n_pii} PII column(s) | Tier: {tier}")
        if pii.get("restricted_columns_found"):
            print(f"    ⚠ RESTRICTED columns — LOAD BLOCKED")
        if pii.get("findings"):
            for col, info in pii["findings"].items():
                method = info.get("method","?")
                print(f"    {col:20} → {info.get('pii_type','?'):20} ({info.get('sensitivity','?')}) [{method}]")

        # Quality Agent result
        qual   = result.get("quality_result", {})
        total  = qual.get("total_rows", 0)
        clean  = qual.get("clean_rows", 0)
        quar   = qual.get("quarantined_rows", 0)
        qpct   = qual.get("quarantine_pct", 0)
        ge_src = qual.get("ge_suite_source", "?")
        print(f"\n  QUALITY AGENT   : {clean}/{total} clean | {quar} quarantined ({qpct}%)")
        print(f"    GE suite      : {ge_src}")
        print(f"    Checks passed : {qual.get('checks_passed','?')}/{qual.get('checks_passed',0)+qual.get('checks_failed',0)}")

        # RAG memory context
        if schema.get("memory_context") and "No past" not in schema.get("memory_context",""):
            print(f"\n  RAG MEMORY USED : Schema agent retrieved past incidents")
        if pii.get("memory_context") and "No past" not in pii.get("memory_context",""):
            print(f"  RAG MEMORY USED : PII agent retrieved past findings")

        # Final decision
        decision = result.get("load_decision", "?")
        alert    = result.get("alert_fired", False)
        print()
        print_separator("-")
        print(f"  LOAD DECISION   : {decision.upper()}")
        print(f"  ALERT FIRED     : {'YES ⚠' if alert else 'No'}")
        print(f"  TOTAL DURATION  : {elapsed}s")
        print_separator()

        if watch:
            print("\n  Watching pipeline status (Ctrl+C to stop)...")
            for _ in range(12):
                time.sleep(5)
                try:
                    status_resp = requests.get(f"http://{ec2_ip}:8001/status", timeout=5)
                    status = status_resp.json()
                    print(f"  [{datetime.now().strftime('%H:%M:%S')}] "
                          f"Status: {status.get('status','?')} | "
                          f"Decision: {status.get('load_decision','?')}")
                except Exception:
                    pass

    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] Cannot reach EC2 supervisor at {supervisor_url}")
        print()
        print("  Checks:")
        print("  1. EC2 security group allows inbound TCP 8001 from your IP")
        print("  2. SSH to EC2: sudo systemctl status sigma-supervisor")
        print("  3. EC2 public IP is correct")
    except requests.exceptions.Timeout:
        print("  [ERROR] Pipeline timed out (>180s)")
        print("  SSH to EC2 and check: journalctl -u sigma-supervisor -f")
    except Exception as e:
        print(f"  [ERROR] {e}")

def main():
    parser = argparse.ArgumentParser(description="Sigma Platform Pipeline Trigger")
    parser.add_argument("--ec2-ip",      required=True, help="EC2 public IP address")
    parser.add_argument("--bucket",      default="sigma-datatech-team",
                        help="S3 bucket name (default: sigma-datatech-team)")
    parser.add_argument("--prefix",      default="bronze/transactions/",
                        help="S3 prefix (default: bronze/transactions/)")
    parser.add_argument("--watch",       action="store_true",
                        help="Watch pipeline status after triggering")
    parser.add_argument("--health-check",action="store_true",
                        help="Check health of all services and exit")
    args = parser.parse_args()

    if args.health_check:
        health_check(args.ec2_ip)
        return

    # Always do a quick health check before triggering
    print(f"  Checking services on {args.ec2_ip}...")
    try:
        resp = requests.get(f"http://{args.ec2_ip}:8001/health", timeout=5)
        if resp.status_code != 200:
            print(f"  [WARN] Supervisor not healthy (HTTP {resp.status_code})")
            print("  Run: python trigger.py --ec2-ip <ip> --health-check")
    except Exception:
        print(f"  [ERROR] Supervisor not reachable at {args.ec2_ip}:8001")
        print("  Run: python trigger.py --ec2-ip <ip> --health-check")
        sys.exit(1)

    trigger_pipeline(args.ec2_ip, args.bucket, args.prefix, args.watch)

if __name__ == "__main__":
    main()
