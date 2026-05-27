# Day 8 — DevOps + Quality Brain

**"Test it. Guard it. Automate it."**

## Quick Start

```bash
cd repo/day8/lab
pip install -r requirements.txt
python 0_setup_duckdb.py       # creates sigma_platform.duckdb — run this first
python 1_code_review.py        # Sprint 1: AI code review + RCA
python 2_doc_generator.py      # Sprint 2: AI generates docs + runbook
python 3_testing_sprint.py     # Sprint 3: AI generates pytest + GE checks
python 4_ci_slo.py             # Sprint 4: AI generates GitHub Actions + SLOs
python 5_observability.py      # Sprint 5: Evidently drift dashboard
python 6_competitive_build.py  # Final: Ship or Reject verdict
```

## Validate & Push

```bash
cd repo/day8
python tests/validate.py
git add .
git commit -m "Day 8 done — DevOps + Quality Brain"
git push
```

## Tools Learned

| Tool | Purpose | License |
|------|---------|---------|
| DuckDB | Local analytical database | MIT |
| pytest | Code testing | MIT |
| Great Expectations | Data quality checks | Apache 2.0 |
| evidently | ML observability + drift detection | Apache 2.0 |
| ruff | Python linter (Rust-based) | MIT |
| GitHub Actions | CI/CD automation | Free (public repos) |
