-- dim_customers.sql
-- Dimension: customer master with PII masked for analytics use
-- NOTE: Raw PII (email, phone, pan) is hashed — never expose in downstream reporting

{{ config(materialized='table') }}

SELECT
    customer_id,
    account_tier,
    kyc_status,
    DATE_TRUNC('month', date_of_birth)                  AS birth_month,
    DATEDIFF('year', date_of_birth, CURRENT_DATE())     AS age_years,
    registration_date,
    last_login_at,
    is_active,
    SHA2(customer_email, 256)                           AS customer_email_hash,
    SHA2(customer_phone, 256)                           AS customer_phone_hash,
    SHA2(pan_number, 256)                               AS pan_hash,
    -- Raw PII fields intentionally excluded from this model
    -- Access to raw PII requires stg_customers (Finance + Compliance only)
    CURRENT_TIMESTAMP()                                 AS _loaded_at
FROM {{ ref('stg_customers') }}
WHERE is_active = TRUE
