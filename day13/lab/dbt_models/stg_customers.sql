-- stg_customers.sql
-- Staging: customer master data from raw CRM export

{{ config(materialized='view') }}

SELECT
    customer_id,
    first_name,
    last_name,
    customer_email,
    customer_phone,
    date_of_birth,
    home_address,
    pan_number,
    kyc_status,
    registration_date,
    last_login_at,
    account_tier,
    is_active,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'customers') }}
WHERE customer_id IS NOT NULL
