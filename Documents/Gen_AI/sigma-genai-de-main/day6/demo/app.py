"""
Day 6 Lab: SQL Brain — AI-Powered SQL Review & dbt Scaffolding
Sigma DataTech · GenAI for Data Engineering · Sigmoid Bangalore 2026
"""

import time
import json
import streamlit as st

from helpers import call_llm, Usage
from sample_data import (
    SIGMA_SCHEMA, SIGMA_SCHEMA_COMPACT, BROKEN_QUERIES,
    NL2SQL_EXAMPLES, DBT_PROJECT_STRUCTURE, DBT_TEST_SCENARIOS,
)

st.set_page_config(
    page_title="Day 6 · SQL Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
body, .stMarkdown, .stText { font-size: 16px !important; }
h1 { font-size: 28px !important; }
h2 { font-size: 22px !important; }
h3 { font-size: 19px !important; }

.mission-banner {
    background: linear-gradient(135deg, #1a2f5e 0%, #2563eb 100%);
    border-radius: 14px;
    padding: 22px 28px;
    margin-bottom: 24px;
    color: white;
}
.mission-banner h2 { color: white !important; margin: 0 0 6px 0; font-size: 24px !important; }
.mission-banner .tagline { font-size: 15px; opacity: 0.85; margin-bottom: 12px; }
.mission-banner .learn-tag {
    background: rgba(255,255,255,0.15);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 13px;
    font-weight: 600;
    display: inline-block;
}

.step-row {
    display: flex; align-items: flex-start; gap: 14px;
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;
}
.step-num {
    background: #2563eb; color: white;
    width: 30px; height: 30px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 14px; flex-shrink: 0;
}
.step-text { flex: 1; line-height: 1.5; color: #1e293b !important; font-size: 15px; }
.step-text b { color: #1e3a8a !important; }

.concept-box {
    background: #eef2ff; border-left: 5px solid #4f46e5;
    padding: 1rem 1.2rem; border-radius: 0 8px 8px 0;
    margin-bottom: 1.2rem; color: #1e1b4b !important; font-size: 15px;
}
.notice-box {
    background: #fef9c3; border: 2px solid #ca8a04;
    border-radius: 10px; padding: 14px 18px;
    margin-top: 16px; color: #1c1917 !important; font-size: 15px;
}
.notice-box b { color: #78350f !important; }

.bug-card {
    background: #fef2f2; border-left: 4px solid #dc2626;
    padding: 10px 14px; border-radius: 0 8px 8px 0;
    margin-bottom: 8px; font-size: 14px; color: #1c1917 !important;
}
.fix-card {
    background: #f0fdf4; border-left: 4px solid #16a34a;
    padding: 10px 14px; border-radius: 0 8px 8px 0;
    margin-bottom: 8px; font-size: 14px; color: #1c1917 !important;
}

.bedrock-pill {
    background: #fff7ed; color: #c2410c;
    border: 1px solid #fdba74; border-radius: 20px;
    padding: 3px 12px; font-size: 12px; font-weight: 700;
    display: inline-block; margin-bottom: 4px;
}
.ollama-pill {
    background: #dcfce7; color: #15803d;
    border: 1px solid #86efac; border-radius: 20px;
    padding: 3px 12px; font-size: 12px; font-weight: 700;
    display: inline-block; margin-bottom: 4px;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────────────────────
def mission_banner(emoji, title, tagline, learn):
    st.markdown(f"""
    <div class="mission-banner">
        <h2>{emoji} {title}</h2>
        <div class="tagline">{tagline}</div>
        <span class="learn-tag">What you'll learn: {learn}</span>
    </div>
    """, unsafe_allow_html=True)


def show_steps(steps):
    for i, (title, desc) in enumerate(steps, 1):
        st.markdown(f"""
        <div class="step-row">
            <div class="step-num">{i}</div>
            <div class="step-text"><b>{title}</b> — {desc}</div>
        </div>
        """, unsafe_allow_html=True)


def notice_box(text):
    st.markdown(f'<div class="notice-box"><b>Key Insight:</b> {text}</div>',
                unsafe_allow_html=True)


def backend_pill():
    if get_backend() == "ollama":
        st.markdown(f'<span class="ollama-pill">Ollama {get_model()}</span>',
                    unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="bedrock-pill">Bedrock {get_model()}</span>',
                    unsafe_allow_html=True)


def get_backend():
    return st.session_state.get("backend", "bedrock")


def get_model():
    if get_backend() == "ollama":
        return st.session_state.get("ollama_model", "qwen2.5:7b")
    return st.session_state.get("bedrock_model", "amazon.nova-lite-v1:0")


def run_llm(system, user_msg, max_tokens=2000):
    t0 = time.perf_counter()
    label = f"Calling {get_model()}..."
    with st.spinner(label):
        text, usage_or_err = call_llm(
            system, user_msg,
            backend=get_backend(),
            model=get_model(),
            max_tokens=max_tokens,
        )
    elapsed = time.perf_counter() - t0
    if text is None:
        st.error(f"LLM call failed: {usage_or_err}")
        return None, None, 0
    return text, usage_or_err, elapsed


def show_usage(usage, elapsed):
    if usage and isinstance(usage, Usage):
        cols = st.columns(3)
        cols[0].metric("Input tokens", f"{usage.input_tokens:,}")
        cols[1].metric("Output tokens", f"{usage.output_tokens:,}")
        cols[2].metric("Response time", f"{elapsed:.1f}s")


# ── Sidebar ──────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.title("SQL Brain")
        st.caption("Day 6 | Sigma DataTech | Sigmoid Bangalore")
        st.divider()

        st.subheader("Setup")
        backend = st.radio(
            "LLM Backend:",
            ["AWS Bedrock (Corporate)", "Ollama Local (Fallback)"],
            index=0,
        )
        st.session_state.backend = "bedrock" if "Bedrock" in backend else "ollama"

        if get_backend() == "bedrock":
            st.session_state.bedrock_model = st.radio(
                "Model:", ["amazon.nova-lite-v1:0", "amazon.nova-pro-v1:0"],
                captions=["Fast, good for SQL tasks", "Stronger reasoning"],
                index=0,
            )
            st.caption("Uses your AWS credentials (aws configure)")
        else:
            st.session_state.ollama_model = st.radio(
                "Model:", ["qwen2.5:7b", "qwen2.5:14b"],
                captions=["8 GB RAM", "16 GB RAM"],
                index=0,
            )
            st.caption("Run: ollama serve")

        st.divider()
        st.subheader("Modules")
        module = st.radio(
            "Navigate:",
            [
                "Home",
                "1. SQL Review Agent",
                "2. NL2SQL Generation",
                "3. dbt Scaffolding",
                "4. AI-Generated Tests",
            ],
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("Validate: python day6/tests/validate_day6.py")
        return module


# ══════════════════════════════════════════════════════════════════════════════
#  HOME
# ══════════════════════════════════════════════════════════════════════════════
def page_home():
    st.title("SQL Brain — AI-Powered SQL Review & dbt Architecture")
    st.markdown("#### Day 6 | Sigma Intelligence Platform | Module 1 of 8")
    st.divider()

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("""
        ### Your Mission Today

        You're a Data Engineer at **Sigma DataTech**. The analytics team just
        handed you three SQL queries for a board meeting tomorrow. They "work"
        — but do they produce correct results?

        **Old way:** Spend 2 days reviewing manually, hope you catch the bugs.

        **New way (today):** Build an AI-powered SQL review system that catches bugs,
        generates optimised SQL, scaffolds dbt projects, and auto-generates tests —
        all in one afternoon.

        ---

        ### What You'll Build (Progressive)

        | Module | What | Outcome |
        |--------|------|---------|
        | 1 | SQL Review Agent | Feed broken SQL to AI, get structured review |
        | 2 | NL2SQL Generator | Type English, get production SQL |
        | 3 | dbt Scaffolding | AI generates full dbt project structure |
        | 4 | AI-Generated Tests | dbt schema tests — including ones that SHOULD fail |

        By end of day: a complete `/sql_brain/` folder that becomes part of
        the Sigma Intelligence Platform you'll build over the next 8 days.
        """)

    with col2:
        st.markdown("### Why This Matters at Scale")
        st.info("""
**Real production stats:**
- Average DE reviews 50+ SQL queries/week
- 23% of production SQL has at least one logic bug (silent wrong results)
- dbt projects with AI-generated tests catch 3x more issues before production

**Today's goal:**
Build the muscle memory of using AI as your senior SQL reviewer — not replacing your brain, but extending it.
        """)

        st.markdown("### Submission")
        st.success("""
**Run the validator before pushing:**
```
python day6/tests/validate_day6.py
```
All tests green → `git push` → you're done.
        """)


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 1 — SQL REVIEW AGENT
# ══════════════════════════════════════════════════════════════════════════════
def page_sql_review():
    mission_banner(
        "1", "SQL Review Agent",
        "Feed broken SQL to AI and get a structured code review — bugs, performance issues, security risks.",
        "How to prompt AI for structured SQL review (the pattern you'll reuse in your capstone)"
    )
    backend_pill()

    show_steps([
        ("Pick a broken query", "We've prepared 3 queries with real bugs — the kind that pass syntax checks but produce WRONG results."),
        ("Read the SQL carefully", "Before running AI review, take 60 seconds to spot bugs yourself. How many can you find?"),
        ("Run AI Review", "The AI gets your SQL + schema + a structured review prompt. Watch the prompt carefully — this is a production-grade review prompt."),
        ("Compare your findings", "Did AI catch bugs you missed? Did you catch something AI missed? That's the sweet spot."),
    ])

    st.divider()

    # Concept box
    st.markdown("""
    <div class="concept-box">
    <b>Why LLMs are good at SQL review:</b> LLMs trained on millions of SQL examples
    have seen every anti-pattern. They excel at: (1) spotting implicit JOIN issues,
    (2) finding logic errors in WHERE/HAVING, (3) identifying performance anti-patterns.
    They struggle with: business context (is this the RIGHT metric?) and schema-specific edge cases.
    </div>
    """, unsafe_allow_html=True)

    # Select query
    query_name = st.selectbox("Select a broken query to review:", list(BROKEN_QUERIES.keys()))
    query_data = BROKEN_QUERIES[query_name]

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown(f"### SQL to Review: *{query_name}*")
        sql_input = st.text_area(
            "SQL (you can edit this):",
            value=query_data["sql"],
            height=250,
            key="review_sql",
        )

    with col2:
        st.markdown("### Your Turn First")
        st.warning(f"**Severity hint:** {query_data['severity']}")
        st.markdown("Before clicking Run, try to spot the bugs yourself:")
        user_bugs = st.text_area(
            "What bugs do you see? (optional — for your own learning)",
            height=100,
            placeholder="e.g., Missing WHERE filter, wrong JOIN type...",
            key="user_bugs",
        )

    # The review prompt
    review_system = """You are a senior Data Engineer performing a code review on SQL queries.
You review for: correctness (logic bugs), performance (anti-patterns), security (PII exposure, injection),
and readability (naming, formatting, comments).

For each issue found, output this exact structure:
## Issue N: [title]
- **Severity:** Critical / High / Medium / Low
- **Category:** Logic Bug / Performance / Security / Readability
- **Line:** [approximate line number]
- **Problem:** [1-2 sentence explanation]
- **Fix:** [exact corrected SQL snippet]

After all issues, provide:
## Corrected Query
[The complete fixed SQL]

## Summary
- Total issues: N
- Critical: N | High: N | Medium: N | Low: N"""

    review_user = f"""Review this SQL query against the following schema.

SCHEMA:
{SIGMA_SCHEMA_COMPACT}

SQL TO REVIEW:
```sql
{sql_input}
```

Find ALL bugs (logic, performance, security, readability). Be thorough."""

    # Show the prompt
    with st.expander("See the exact prompt sent to AI (this IS the learning)"):
        st.markdown("**SYSTEM (Role):**")
        st.code(review_system, language="text")
        st.markdown("**USER (Question):**")
        st.code(review_user, language="text")

    if st.button("Run AI Review", type="primary", key="run_review"):
        text, usage, elapsed = run_llm(review_system, review_user, max_tokens=2000)
        if text:
            st.markdown("---")
            st.markdown("### AI Review Results")
            st.markdown(text)
            show_usage(usage, elapsed)

            # Show the actual bugs for comparison
            st.markdown("---")
            st.markdown("### Known Bugs (Compare with AI's findings)")
            for bug in query_data["bugs"]:
                st.markdown(f'<div class="bug-card">{bug}</div>', unsafe_allow_html=True)

            notice_box(
                "Compare AI's findings with the known bugs above. "
                "Did AI find all of them? Did it find EXTRA issues you didn't expect? "
                "A good AI review catches 80-90% of real bugs. The remaining 10-20% need human domain knowledge."
            )

    # Screenshot reminder
    st.markdown("---")
    st.info("**Done with Module 1?** Run `python day6/tests/validate_day6.py` to check your sql_review.py passes.")


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 2 — NL2SQL GENERATION
# ══════════════════════════════════════════════════════════════════════════════
def page_nl2sql():
    mission_banner(
        "2", "NL2SQL — English to Production SQL",
        "Type a business question in plain English. Get production-ready SQL. Learn why schema grounding is everything.",
        "Schema grounding, prompt structure for NL2SQL, and how to validate AI-generated SQL"
    )
    backend_pill()

    show_steps([
        ("Type a business question", "Use plain English — like you're asking a colleague."),
        ("Watch the prompt", "Notice how we give AI the schema. Without it, AI invents table names."),
        ("Run and review", "Is the SQL correct? Does it use the right tables and columns?"),
        ("Try the 'bad prompt' toggle", "See what happens when you remove schema grounding."),
    ])

    st.divider()

    # Concept
    st.markdown("""
    <div class="concept-box">
    <b>NL2SQL accuracy depends on prompt quality:</b><br>
    - No schema provided: ~30% accuracy (AI guesses table names)<br>
    - Schema provided: ~75% accuracy<br>
    - Schema + examples + dialect specified: ~90% accuracy<br>
    The schema IS the secret. Always ground your NL2SQL prompts with the actual DDL or compact schema.
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        question = st.text_area(
            "Business question (plain English):",
            value=NL2SQL_EXAMPLES[0],
            height=80,
            key="nl2sql_q",
        )
        st.caption("Try these examples:")
        for ex in NL2SQL_EXAMPLES[1:]:
            st.caption(f"  - {ex}")

    with col2:
        dialect = st.selectbox("SQL Dialect:", ["Snowflake", "PostgreSQL", "Spark SQL"])
        grounded = st.toggle("Include schema (grounding)", value=True)
        if not grounded:
            st.warning("Schema removed! Watch how output quality drops.")

    # Build prompt
    nl2sql_system = f"""You are a senior Data Engineer writing production {dialect} SQL.
Rules:
- Use ONLY tables and columns from the provided schema
- Use explicit JOINs (never implicit comma joins)
- Add comments explaining complex logic
- Use CTEs for readability when query has 2+ joins
- Return ONLY the SQL in a code block — no explanation before or after"""

    schema_section = f"\nSCHEMA:\n{SIGMA_SCHEMA_COMPACT}" if grounded else "\n(No schema provided — generate best guess)"
    nl2sql_user = f"""{schema_section}

QUESTION: {question}

Generate production-ready {dialect} SQL."""

    with st.expander("See the exact prompt"):
        st.code(nl2sql_system, language="text")
        st.code(nl2sql_user, language="text")

    if st.button("Generate SQL", type="primary", key="run_nl2sql"):
        text, usage, elapsed = run_llm(nl2sql_system, nl2sql_user, max_tokens=1500)
        if text:
            st.markdown("### Generated SQL")
            st.markdown(text)
            show_usage(usage, elapsed)

            if not grounded:
                notice_box(
                    "Without schema grounding, the AI likely invented table names or used wrong column names. "
                    "Toggle schema back ON and run the same question — compare the difference. "
                    "This is why production NL2SQL systems ALWAYS include schema context."
                )
            else:
                notice_box(
                    "Check: (1) Are table names correct? (2) Are JOIN conditions right? "
                    "(3) Does the WHERE clause match your intent? "
                    "If all three pass, this SQL is production-ready. "
                    "Now try toggling OFF the schema to see what happens without grounding."
                )


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 3 — dbt SCAFFOLDING
# ══════════════════════════════════════════════════════════════════════════════
def page_dbt_scaffold():
    mission_banner(
        "3", "dbt Project Scaffolding",
        "AI generates a complete dbt project structure: models, sources, schema tests — from a single prompt.",
        "How AI accelerates dbt development from days to minutes (and what you still need to review)"
    )
    backend_pill()

    show_steps([
        ("Understand dbt structure", "A dbt project has models (SQL), schema files (YAML), and tests. AI generates all three."),
        ("Choose what to generate", "Start with a staging model, then add intermediate and mart layers."),
        ("Run generation", "AI produces the SQL + YAML files. Review them — are the column names right?"),
        ("Review critically", "AI often gets 80% right. Your job is to catch the 20% — wrong joins, missing filters, made-up columns."),
    ])

    st.divider()

    # Concept
    st.markdown("""
    <div class="concept-box">
    <b>Why dbt + AI is powerful:</b> dbt enforces structure (staging → intermediate → marts).
    AI fills that structure with actual SQL. The combination means you go from "I need a merchant
    performance dashboard" to a tested, documented, production-deployable dbt project in under an hour.
    The catch: AI doesn't know your business rules. "Revenue" might mean different things to different teams.
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"```\n{DBT_PROJECT_STRUCTURE}\n```")

    gen_type = st.radio(
        "What to generate:",
        ["Staging model (stg_transactions.sql)", "Mart model (mart_merchant_performance.sql)",
         "Full schema.yml with sources + docs", "Complete dbt project (all files)"],
        index=0,
        key="dbt_gen_type",
    )

    dbt_system = """You are a senior Analytics Engineer specializing in dbt.
Generate production-quality dbt code following these conventions:
- Use CTEs for readability
- Prefix staging models with stg_, intermediate with int_, marts with mart_
- Include column descriptions in schema.yml
- Add appropriate dbt tests (not_null, unique, accepted_values, relationships)
- Use Jinja ref() and source() macros correctly
- Add model-level description explaining business purpose"""

    prompts = {
        "Staging model (stg_transactions.sql)": f"""Generate a dbt staging model for the transactions table.

Source table: sigma_analytics.fact_transactions
Columns: {SIGMA_SCHEMA_COMPACT.split(chr(10))[0]}

The staging model should:
1. Rename columns to snake_case business names
2. Cast types explicitly
3. Add a surrogate key using dbt_utils.generate_surrogate_key
4. Filter out test/internal transactions (merchant_id starting with 'TEST_')
5. Include the model SQL and the corresponding schema.yml entry""",

        "Mart model (mart_merchant_performance.sql)": f"""Generate a dbt mart model: mart_merchant_performance

This model should aggregate merchant-level KPIs for dashboard consumption.
Available upstream models: stg_transactions, stg_merchants, stg_customers

Required output columns:
- merchant_id, merchant_name, category, city
- total_revenue (only COMPLETED transactions)
- total_transactions, failed_transactions
- failure_rate_pct
- avg_transaction_value
- unique_customers
- first_transaction_date, last_transaction_date

Use CTEs. Include schema.yml with tests.""",

        "Full schema.yml with sources + docs": f"""Generate a complete schema.yml for a dbt project with these sources:

Source database: sigma_analytics
Tables:
{SIGMA_SCHEMA_COMPACT}

Include:
1. Source definition with database/schema
2. Table-level descriptions (business purpose)
3. Column-level descriptions
4. Tests: not_null on PKs, unique on PKs, accepted_values on status/tier columns
5. Freshness checks (warn_after 12 hours, error_after 24 hours)""",

        "Complete dbt project (all files)": f"""Generate a complete dbt project for Sigma DataTech analytics.

Schema:
{SIGMA_SCHEMA_COMPACT}

Generate ALL of these files (show each with its path):
1. dbt_project.yml (project config)
2. models/staging/stg_transactions.sql
3. models/staging/stg_merchants.sql
4. models/staging/schema.yml (sources + staging tests)
5. models/marts/mart_merchant_performance.sql
6. models/marts/schema.yml (mart tests + docs)

Follow dbt best practices. Use ref() and source() correctly.""",
    }

    dbt_user = prompts[gen_type]

    with st.expander("See the exact prompt"):
        st.code(dbt_system, language="text")
        st.code(dbt_user, language="text")

    if st.button("Generate dbt Code", type="primary", key="run_dbt"):
        max_tok = 3000 if "Complete" in gen_type else 2000
        text, usage, elapsed = run_llm(dbt_system, dbt_user, max_tokens=max_tok)
        if text:
            st.markdown("### Generated dbt Code")
            st.markdown(text)
            show_usage(usage, elapsed)

            notice_box(
                "Review checklist: (1) Are ref() calls pointing to real model names? "
                "(2) Do column names match your schema? (3) Are business rules correct "
                "(e.g., revenue = only COMPLETED status)? "
                "AI gets structure right 95% of the time. Business logic is where you add value."
            )

    st.markdown("---")
    st.info("**Done with Module 3?** Run `python day6/tests/validate_day6.py` to check your dbt_generator.py passes.")


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 4 — AI-GENERATED TESTS
# ══════════════════════════════════════════════════════════════════════════════
def page_dbt_tests():
    mission_banner(
        "4", "AI-Generated dbt Tests",
        "AI writes schema tests — including ones designed to FAIL. A failing test is a GOOD thing: it means your safety net works.",
        "How to use AI to generate comprehensive test suites, and why deliberate failures prove your tests work"
    )
    backend_pill()

    show_steps([
        ("Understand dbt test types", "not_null, unique, accepted_values, relationships — each catches a different class of bug."),
        ("Generate tests for your model", "AI analyses the schema and produces a full test suite."),
        ("The Deliberate Failure", "We'll generate a test that SHOULD fail on bad data. This proves the test actually catches problems."),
        ("Review: useful vs useless tests", "Not all AI-generated tests are worth keeping. Learn to spot the useless ones."),
    ])

    st.divider()

    # Concept: test types
    st.markdown("### dbt Test Types at a Glance")
    cols = st.columns(4)
    for i, (test_name, test_data) in enumerate(DBT_TEST_SCENARIOS.items()):
        with cols[i]:
            st.markdown(f"**{test_name}**")
            st.caption(test_data["description"])
            st.code(test_data["example"], language="yaml")

    st.divider()

    # Generate tests
    st.markdown("### Generate Full Test Suite")

    test_target = st.radio(
        "Generate tests for:",
        ["fact_transactions (source table)", "stg_transactions (staging model)",
         "mart_merchant_performance (mart)"],
        key="test_target",
    )

    test_system = """You are a senior Analytics Engineer writing dbt schema tests.
Generate comprehensive tests that catch real production issues.
For each test, include a brief comment explaining WHAT it catches and WHY it matters.
Output valid dbt schema.yml format."""

    test_user = f"""Generate a complete dbt schema.yml test suite for: {test_target}

Schema context:
{SIGMA_SCHEMA_COMPACT}

Requirements:
1. Include all standard tests (not_null, unique, accepted_values, relationships)
2. Add at least one custom test using dbt_utils (e.g., expression_is_true)
3. For ONE test, add a comment saying "THIS TEST SHOULD FAIL on bad data" — design it so that
   if someone inserts a row with status='CANCELLED' (not in accepted values), this test catches it.
4. Include test severity levels (warn vs error)
5. Add a test that checks no future dates exist in transaction_date

Output the full schema.yml content."""

    with st.expander("See the exact prompt"):
        st.code(test_system, language="text")
        st.code(test_user, language="text")

    if st.button("Generate Test Suite", type="primary", key="run_tests"):
        text, usage, elapsed = run_llm(test_system, test_user, max_tokens=2000)
        if text:
            st.markdown("### Generated Test Suite")
            st.markdown(text)
            show_usage(usage, elapsed)

            notice_box(
                "Find the test marked 'SHOULD FAIL'. This is deliberate — "
                "it proves your safety net works. In production, when someone accidentally "
                "loads data with an unexpected status value, THIS test will fire an alert "
                "before bad data reaches dashboards. A test that never fails is useless."
            )

    st.divider()

    # Deliberate failure demonstration
    st.markdown("### The Deliberate Failure Experiment")
    st.markdown("""
    Here's the key insight: **a test suite that always passes might not be testing anything useful.**

    In production, you WANT to see tests fail during development — it proves they work.
    The sequence:
    1. Generate tests against good data (all pass)
    2. Insert one bad row (status = 'CANCELLED')
    3. Run tests again — `accepted_values` test fails
    4. That failure = proof your safety net works
    """)

    fail_system = """You are explaining data quality testing to junior engineers.
Show the exact sequence of what happens when a dbt test catches bad data."""

    fail_user = """Show me a concrete example of the deliberate failure pattern:

1. The dbt test definition (accepted_values for status column)
2. The SQL that dbt actually runs behind the scenes for this test
3. What the output looks like when it PASSES (good data)
4. What the output looks like when it FAILS (bad row with status='CANCELLED')
5. Why this failure is a GOOD thing (what disaster it prevented)

Use the sigma_analytics.fact_transactions table. Be specific with row counts and values."""

    if st.button("Show Deliberate Failure Example", key="run_fail"):
        text, usage, elapsed = run_llm(fail_system, fail_user, max_tokens=1500)
        if text:
            st.markdown(text)
            show_usage(usage, elapsed)

    st.markdown("---")
    st.info("**All modules done?** Run `python day6/tests/validate_day6.py` — all green → `git push`")


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTER
# ══════════════════════════════════════════════════════════════════════════════
def main():
    module = render_sidebar()

    if "Home" in module:
        page_home()
    elif "SQL Review" in module:
        page_sql_review()
    elif "NL2SQL" in module:
        page_nl2sql()
    elif "dbt Scaffolding" in module:
        page_dbt_scaffold()
    elif "Tests" in module:
        page_dbt_tests()


if __name__ == "__main__":
    main()
