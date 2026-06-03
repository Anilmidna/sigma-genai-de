-- dim_merchants.sql
-- Dimension: merchant master — slowly changing, enriched with performance tier

{{ config(materialized='table') }}

SELECT
    m.merchant_id,
    m.merchant_name,
    m.business_category,
    m.merchant_city,
    m.merchant_state,
    m.gstin,
    m.contact_email,
    m.onboarding_date,
    m.contract_start_date,
    m.contract_end_date,
    m.sla_threshold_inr,
    m.is_active,
    COALESCE(p.merchant_tier, 'BRONZE')                 AS current_tier,
    COALESCE(p.gmv_30d_inr, 0)                          AS gmv_30d_inr,
    COALESCE(p.avg_failure_rate_pct, 0)                 AS failure_rate_30d_pct,
    m._loaded_at
FROM {{ ref('stg_merchants') }} m
LEFT JOIN {{ ref('int_merchant_performance') }} p
    ON m.merchant_id = p.merchant_id
WHERE m.is_active = TRUE
