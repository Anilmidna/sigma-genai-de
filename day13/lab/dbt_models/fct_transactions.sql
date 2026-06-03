-- fct_transactions.sql
-- Fact: enriched transaction events — the single source of truth for all reporting

{{ config(materialized='incremental', unique_key='transaction_id') }}

SELECT
    t.transaction_id,
    t.transaction_date,
    t.customer_id,
    c.account_tier                   AS customer_tier,
    t.merchant_id,
    m.merchant_name,
    m.business_category,
    m.merchant_city,
    t.amount,
    t.currency,
    t.payment_method,
    t.transaction_status,
    t.failure_reason,
    CASE WHEN t.transaction_status = 'completed' THEN t.amount ELSE 0 END AS gmv_contribution,
    t._loaded_at
FROM {{ ref('stg_transactions') }} t
LEFT JOIN {{ ref('stg_customers') }} c
    ON t.customer_id = c.customer_id
LEFT JOIN {{ ref('stg_merchants') }} m
    ON t.merchant_id = m.merchant_id

{% if is_incremental() %}
WHERE t._loaded_at > (SELECT MAX(_loaded_at) FROM {{ this }})
{% endif %}
