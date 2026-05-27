# Team 9 — Runbook Guardian

## Business Context
A Sigma DataTech DE wrote the Silver pipeline. It works. But at 3 AM, when it fails, nobody knows how to run it manually, what to check, or who to call. Your AI guardian will generate the runbook — then a confused junior engineer will try to follow it and ask questions. The questions reveal the gaps.

## Your Module
Build a Streamlit app that:

**Round 1 — AI Runbook Writer:** Nova Pro reads the Silver pipeline code and generates a complete operational runbook: setup, normal run, failure scenarios, validation steps, escalation path.

**Round 2 — Junior Engineer Simulator:** Nova Lite plays a junior engineer reading the runbook for the first time. It asks exactly 5 questions — the ones a real new hire would ask at 3 AM. Some questions are trivial. At least one reveals a genuine gap.

**Round 3 — Your Gap Analysis:** For each question, classify: RUNBOOK GAP (missing info) / GOOD QUESTION (reveals real issue) / UNNECESSARY (already answered). Fix the runbook gaps and show the updated version.

## Deliverables
1. Running Streamlit app showing runbook → junior questions → your gap analysis
2. The updated runbook with gaps fixed
3. The one question that revealed a genuine issue in the pipeline itself (not just the docs)
4. The "What AI Got Wrong" slide — what critical scenario did the runbook miss entirely?

## The Trap
One of the junior engineer's questions will reveal a gap that isn't just documentation — it's a real gap in the pipeline's error handling. The runbook can't document a recovery procedure for a failure mode that doesn't have one. You'll need to propose both a runbook update AND a code fix.

## Pitch Must Include
- Live demo of runbook generation → junior questions → gap analysis
- The question that exposed a real pipeline gap (not just a docs gap)
- Your updated runbook snippet for the most critical gap
- What "production-ready" means beyond just working code
