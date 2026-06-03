-- int_daily_gmv.sql
-- Intermediate: daily gross merchandise value by merchant

{{ config(materialized='table') }}

SELECT
    t.transaction_date,
    t.merchant_id,
    m.merchant_name,
    m.business_category,
    COUNT(t.transaction_id)                                    AS transaction_count,
    SUM(CASE WHEN t.transaction_status = 'completed'
             THEN t.amount ELSE 0 END)                        AS gmv_inr,
    SUM(CASE WHEN t.transaction_status = 'failed'
             THEN t.amount ELSE 0 END)                        AS failed_amount_inr,
    COUNT(CASE WHEN t.transaction_status = 'failed' THEN 1 END) AS failed_count,
    ROUND(
        COUNT(CASE WHEN t.transaction_status = 'failed' THEN 1 END) * 100.0
        / NULLIF(COUNT(t.transaction_id), 0), 2
    )                                                          AS failure_rate_pct
FROM {{ ref('stg_transactions') }} t
JOIN {{ ref('stg_merchants') }} m
    ON t.merchant_id = m.merchant_id
GROUP BY 1, 2, 3, 4
