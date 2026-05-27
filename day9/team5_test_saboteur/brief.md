# Team 5 — Test Saboteur

## Business Context
A new DE joined Sigma DataTech and used AI to generate a pytest suite for the Silver pipeline. The CI is green. Everyone is happy. But 3 days later, a bug ships to prod that the tests should have caught. Someone sabotaged the test suite — not maliciously, but because they trusted AI output without reading it.

## Your Module
Build a Streamlit app that:

**Round 1 — AI Test Generator:** Nova Pro generates 8-10 pytest tests for the Silver pipeline transformation logic. Display each test with its intent.

**Round 2 — AI Test Critic:** Nova Lite reads each generated test and scores it: STRONG / WEAK / USELESS. For WEAK and USELESS tests, it must explain why.

**Round 3 — Your Audit:** Run all tests against DuckDB. Find the test that always passes even when the pipeline is broken. Prove it with a counter-example.

## Deliverables
1. Running Streamlit app showing generated tests → AI critique → your audit
2. The specific test that is the "saboteur" — the one that passes even when it shouldn't
3. A fixed version of the saboteur test
4. The "What AI Got Wrong" slide — how did AI's critique miss the saboteur?

## The Trap
At least one test will have a logical flaw that makes it always pass regardless of input. The AI critic in Round 2 may not catch it — it reads code, it doesn't reason about all possible inputs. You need to think like an adversary: "How would I make this test pass with wrong code?"

## Pitch Must Include
- Live demo of test generation → critique → audit
- The saboteur test displayed prominently with the proof it always passes
- The fixed test side-by-side with the broken one
- How you would prevent this in a real team (process, not just code)
