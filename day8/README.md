# Day 8 — DevOps + Quality Brain

**"Test it. Guard it. Automate it."**

## Quick Start

```bash
cd repo/day8/lab
pip install -r requirements.txt
python 0_setup_duckdb.py       # creates local DuckDB
python 1_pytest_sprint.py      # Sprint 1: AI generates tests
python 2_soda_sprint.py        # Sprint 2: AI generates data checks
python 3_ci_sprint.py          # Sprint 3: AI generates CI/CD
python 4_competitive_build.py  # Final: Ship or Reject verdict
```

## Validate & Push

```bash
cd repo/day8
python tests/validate_day8.py
git add .
git commit -m "Day 8 done — DevOps + Quality Brain"
git push
```

## Tools Learned

| Tool | Purpose | License |
|------|---------|---------|
| DuckDB | Local analytical database | MIT |
| pytest | Code testing | MIT |
| Soda Core | Data quality checks | Apache 2.0 |
| ruff | Python linter (Rust-based) | MIT |
| GitHub Actions | CI/CD automation | Free (public repos) |
