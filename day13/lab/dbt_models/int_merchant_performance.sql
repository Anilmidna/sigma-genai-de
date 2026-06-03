-- int_merchant_performance.sql
-- Intermediate: rolling 30-day merchant performance metrics

{{ config(materialized='table') }}

SELECT
    merchant_id,
    merchant_name,
    business_category,
    SUM(gmv_inr)                                        AS gmv_30d_inr,
    SUM(transaction_count)                              AS transactions_30d,
    AVG(failure_rate_pct)                               AS avg_failure_rate_pct,
    MAX(transaction_date)                               AS last_transaction_date,
    CASE
        WHEN SUM(gmv_inr) >= 1000000 THEN 'PLATINUM'
        WHEN SUM(gmv_inr) >= 500000  THEN 'GOLD'
        WHEN SUM(gmv_inr) >= 100000  THEN 'SILVER'
        ELSE 'BRONZE'
    END                                                 AS merchant_tier
FROM {{ ref('int_daily_gmv') }}
WHERE transaction_date >= DATEADD(day, -30, CURRENT_DATE())
GROUP BY 1, 2, 3
