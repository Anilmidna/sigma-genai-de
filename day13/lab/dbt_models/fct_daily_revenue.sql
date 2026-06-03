-- fct_daily_revenue.sql
-- Fact: daily revenue summary used by Finance and the executive dashboard

{{ config(materialized='table') }}

SELECT
    transaction_date,
    SUM(gmv_inr)                                        AS total_gmv_inr,
    SUM(transaction_count)                              AS total_transactions,
    COUNT(DISTINCT merchant_id)                         AS active_merchants,
    SUM(failed_amount_inr)                              AS total_failed_inr,
    ROUND(AVG(failure_rate_pct), 2)                     AS avg_failure_rate_pct,
    SUM(gmv_inr) - LAG(SUM(gmv_inr))
        OVER (ORDER BY transaction_date)                AS gmv_day_on_day_change,
    ROUND(
        (SUM(gmv_inr) - LAG(SUM(gmv_inr)) OVER (ORDER BY transaction_date))
        / NULLIF(LAG(SUM(gmv_inr)) OVER (ORDER BY transaction_date), 0) * 100
    , 2)                                                AS gmv_growth_pct
FROM {{ ref('int_daily_gmv') }}
GROUP BY 1
ORDER BY 1 DESC
