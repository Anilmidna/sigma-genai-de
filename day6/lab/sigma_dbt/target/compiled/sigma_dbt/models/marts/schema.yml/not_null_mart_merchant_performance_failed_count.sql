
    
    



with __dbt__cte__stg_transactions as (
-- stg_transactions.sql
-- Staging model: cleans and standardises FACT_TRANSACTIONS from Snowflake source.
-- status and payment_method are kept UPPERCASE to match accepted_values tests.
-- Filters out TEST_ merchant records.

WITH cleaned_transactions AS (
    SELECT
        LOWER(transaction_id)          AS transaction_id,
        CAST(amount AS DECIMAL(10, 2)) AS amount,
        UPPER(status)                  AS status,
        LOWER(merchant_id)             AS merchant_id,
        LOWER(customer_id)             AS customer_id,
        CAST(transaction_date AS DATE) AS transaction_date,
        UPPER(payment_method)          AS payment_method,
        CURRENT_TIMESTAMP              AS loaded_at
    FROM SIGMA_DE.PUBLIC.fact_transactions
    WHERE merchant_id NOT LIKE 'TEST_%'
)

SELECT * FROM cleaned_transactions
),  __dbt__cte__mart_merchant_performance as (
-- mart_merchant_performance.sql
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
    FROM __dbt__cte__stg_transactions
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
) select failed_count
from __dbt__cte__mart_merchant_performance
where failed_count is null


