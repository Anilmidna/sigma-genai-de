
  
    

create or replace transient table SIGMA_DE.PUBLIC.mart_merchant_performance
    
    
    
    as (-- mart_merchant_performance.sql
-- Aggregates transaction data per merchant.
-- Reads from stg_transactions (staging model) and dim_merchant source directly.
-- Business rule: revenue = SUM(amount) WHERE status = 'COMPLETED' only.

WITH filtered_transactions AS (
    SELECT
        transaction_id,
        amount,
        status,
        merchant_id,
        customer_id,
        transaction_date,
        payment_method
    FROM SIGMA_DE.PUBLIC.stg_transactions
    WHERE status IN ('COMPLETED', 'FAILED')
),

merchant_details AS (
    SELECT
        MERCHANT_ID,
        MERCHANT_NAME,
        CATEGORY,
        CITY
    FROM SIGMA_DE.PUBLIC.dim_merchant
),

aggregated_metrics AS (
    SELECT
        ft.merchant_id,
        COUNT(ft.transaction_id)                                              AS total_transactions,
        SUM(CASE WHEN ft.status = 'FAILED'    THEN 1 ELSE 0 END)             AS failed_count,
        SUM(CASE WHEN ft.status = 'COMPLETED' THEN ft.amount ELSE 0 END)     AS total_revenue,
        AVG(CASE WHEN ft.status = 'COMPLETED' THEN ft.amount ELSE NULL END)  AS avg_transaction_value,
        COUNT(DISTINCT ft.customer_id)                                        AS unique_customers
    FROM filtered_transactions ft
    GROUP BY ft.merchant_id
)

SELECT
    md.MERCHANT_ID        AS merchant_id,
    md.MERCHANT_NAME      AS merchant_name,
    md.CATEGORY           AS category,
    md.CITY               AS city,
    am.total_transactions,
    am.failed_count,
    am.total_revenue,
    am.avg_transaction_value,
    am.unique_customers,
    ROUND(
        (am.failed_count::DECIMAL / NULLIF(am.total_transactions, 0)) * 100,
        2
    ) AS failure_rate_pct
FROM aggregated_metrics am
JOIN merchant_details md ON LOWER(am.merchant_id) = LOWER(md.MERCHANT_ID)
ORDER BY am.total_revenue DESC
    )
;


  