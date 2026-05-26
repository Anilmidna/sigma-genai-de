-- ============================================================
-- TRAINER SETUP — Run this ONCE as ACCOUNTADMIN on your Snowflake account
-- This creates the shared student role for Cortex Analyst lab
-- ============================================================

USE ROLE ACCOUNTADMIN;

-- 1. Enable Cortex cross-region (required for Cortex Analyst)
ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION';

-- 2. Create a restricted role for students
CREATE ROLE IF NOT EXISTS STUDENT_CORTEX;

-- 3. Create a shared login for all students
CREATE USER IF NOT EXISTS student_genai
    PASSWORD = 'SigmoidGenAI2026!'
    DEFAULT_ROLE = STUDENT_CORTEX
    DEFAULT_WAREHOUSE = COMPUTE_WH
    DEFAULT_NAMESPACE = SIGMA_DE.PUBLIC
    MUST_CHANGE_PASSWORD = FALSE;

GRANT ROLE STUDENT_CORTEX TO USER student_genai;

-- 4. Grant warehouse access (needed to run queries)
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE STUDENT_CORTEX;

-- 5. Grant database and schema access
GRANT USAGE ON DATABASE SIGMA_DE TO ROLE STUDENT_CORTEX;
GRANT USAGE ON SCHEMA SIGMA_DE.PUBLIC TO ROLE STUDENT_CORTEX;

-- 6. Grant SELECT on all tables (read-only)
GRANT SELECT ON ALL TABLES IN SCHEMA SIGMA_DE.PUBLIC TO ROLE STUDENT_CORTEX;
GRANT SELECT ON FUTURE TABLES IN SCHEMA SIGMA_DE.PUBLIC TO ROLE STUDENT_CORTEX;

-- 7. Grant Cortex AI access
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE STUDENT_CORTEX;

-- 8. Create stage for semantic models (if not exists)
USE DATABASE SIGMA_DE;
USE SCHEMA PUBLIC;

CREATE STAGE IF NOT EXISTS SEMANTIC_MODELS
    DIRECTORY = (ENABLE = TRUE)
    COMMENT = 'Stores semantic model YAML files for Cortex Analyst';

-- 9. Grant stage access (students need to upload their YAML)
GRANT READ, WRITE ON STAGE SIGMA_DE.PUBLIC.SEMANTIC_MODELS TO ROLE STUDENT_CORTEX;

-- 10. Verify setup
SHOW GRANTS TO ROLE STUDENT_CORTEX;

-- ============================================================
-- DONE. Share with students:
--   Account ID: GEJKIOG-TKC55632.snowflakecomputing.com
--   Username:   student_genai
--   Password:   SigmoidGenAI2026!
-- ============================================================
