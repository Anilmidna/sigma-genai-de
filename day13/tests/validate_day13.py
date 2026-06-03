"""
Day 13 Validator — Lineage & Governance Agent (Lab 1 + Lab 2)
Usage: python tests/validate_day13.py
"""
import json, sys
from pathlib import Path

ROOT       = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "lab" / "agent_outputs"
passed = failed = 0

def ok(msg):   global passed; passed += 1; print(f"  OK  {msg}")
def fail(msg): global failed; failed += 1; print(f"  MISSING  {msg}")

print()
print("=" * 55)
print("DAY 13 VALIDATOR — LINEAGE & GOVERNANCE AGENT")
print("=" * 55)

# ── Lab 1: Mystery catalogue ───────────────────────────────────────────────────
print("\nLAB 1 — Mystery Domain:")
cat_a   = OUTPUT_DIR / "catalogue_mystery_a.json"
cat_b   = OUTPUT_DIR / "catalogue_mystery_b.json"
cat_1   = cat_a if cat_a.exists() else (cat_b if cat_b.exists() else None)

if not cat_1:
    fail("No mystery catalogue found — run: python lab/lineage_agent.py --lab 1 --mystery lab/mystery_a/")
else:
    cat    = json.loads(cat_1.read_text())
    tables = cat.get("tables", {})
    ok(f"{cat_1.name} — {len(tables)} tables catalogued")

    pii = cat.get("pii_surface_area", [])
    if len(pii) >= 5:
        ok(f"PII surface area — {len(pii)} columns flagged")
    else:
        fail(f"Too few PII columns ({len(pii)}) — agent may not have completed")

    industry = cat.get("industry_analysis", {}).get("industry", "")
    if industry:
        ok(f"Industry identified: {industry}")
    else:
        fail("Industry not identified")

    if cat.get("three_questions", {}).get("q1_most_damaging_column"):
        ok("Three governance questions answered")
    else:
        fail("Three governance questions missing")

# ── Lab 2: Sigma DataTech catalogue ───────────────────────────────────────────
print("\nLAB 2 — Sigma DataTech (Client Deliverable):")
cat_sigma = OUTPUT_DIR / "catalogue_sigma.json"

if not cat_sigma.exists():
    fail("catalogue_sigma.json not found — run: python lab/lineage_agent.py --lab 2 --models ../day6/sigma_dbt/models/")
else:
    cat    = json.loads(cat_sigma.read_text())
    tables = cat.get("tables", {})
    ok(f"catalogue_sigma.json — {len(tables)} tables catalogued")

    pii = cat.get("pii_surface_area", [])
    if pii:
        ok(f"Sigma DataTech PII surface area — {len(pii)} columns")
    else:
        fail("No PII columns found in Sigma DataTech catalogue")

    if cat.get("three_questions"):
        ok("Governance questions answered for Sigma DataTech")
    else:
        fail("Governance questions missing from Sigma DataTech catalogue")

# ── Manual-first answer ────────────────────────────────────────────────────────
print("\nManual-First Gate:")
guess_path = OUTPUT_DIR / "mystery_guess.json"
if guess_path.exists():
    g = json.loads(guess_path.read_text())
    if g.get("sensitive_columns") or g.get("industry_guess"):
        ok(f"mystery_guess.json saved — lab: {g.get('lab','?')}")
    else:
        fail("mystery_guess.json exists but answers are blank")
else:
    fail("mystery_guess.json not found")

# ── Summary ────────────────────────────────────────────────────────────────────
print()
print("=" * 55)
total = passed + failed
if failed == 0:
    print(f"  STATUS: ALL DONE — {passed}/{total} checks passed")
    print()
    print("  Push to your fork:")
    print("    git add lab/agent_outputs/")
    print('    git commit -m "Day 13 complete — mystery domain + Sigma DataTech governance"')
    print("    git push")
elif failed <= 2:
    print(f"  STATUS: PARTIAL — {passed}/{total} passed")
    print("  Fix missing items above and re-run.")
else:
    print(f"  STATUS: INCOMPLETE — {failed} items missing")
print("=" * 55)
print()
sys.exit(0 if failed == 0 else 1)
