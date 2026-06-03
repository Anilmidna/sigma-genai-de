-- stg_merchants.sql
-- Staging: merchant onboarding data from partner portal

{{ config(materialized='view') }}

SELECT
    merchant_id,
    merchant_name,
    business_category,
    merchant_city,
    merchant_state,
    gstin,
    bank_account_number,
    ifsc_code,
    contact_email,
    contact_phone,
    onboarding_date,
    contract_start_date,
    contract_end_date,
    sla_threshold_inr,
    is_active,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'merchants') }}
WHERE merchant_id IS NOT NULL
