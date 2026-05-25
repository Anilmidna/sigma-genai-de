
    
    



with __dbt__cte__stg_transactions as (
WITH raw_transactions AS (
    SELECT
        transaction_id,
        amount,
        status,
        merchant_id,
        customer_id,
        transaction_date,
        payment_method
    FROM
        SIGMA_DE.PUBLIC.fact_transactions
),

cleaned_transactions AS (
    SELECT
        transaction_id,
        CAST(amount AS DECIMAL(10,2)) AS amount,
        status,
        merchant_id,
        customer_id,
        CAST(transaction_date AS DATE) AS transaction_date,
        payment_method,
        CURRENT_TIMESTAMP AS loaded_at
    FROM
        raw_transactions
    WHERE
        merchant_id NOT LIKE 'TEST_%'
)

SELECT * FROM cleaned_transactions
),  __dbt__cte__mart_merchant_performance as (
WITH completed_transactions AS (
    SELECT
        merchant_id,
        SUM(amount) AS total_revenue,
        COUNT(*) AS total_transactions
    FROM
        __dbt__cte__stg_transactions
    WHERE
        status = 'COMPLETED'
    GROUP BY
        merchant_id
),

failed_transactions AS (
    SELECT
        merchant_id,
        COUNT(*) AS failed_count
    FROM
        __dbt__cte__stg_transactions
    WHERE
        status = 'FAILED'
    GROUP BY
        merchant_id
),

avg_transaction_value AS (
    SELECT
        merchant_id,
        AVG(amount) AS avg_transaction_value
    FROM
        __dbt__cte__stg_transactions
    WHERE
        status = 'COMPLETED'
    GROUP BY
        merchant_id
),

unique_customers AS (
    SELECT
        merchant_id,
        COUNT(DISTINCT customer_id) AS unique_customers
    FROM
        __dbt__cte__stg_transactions
    WHERE
        status = 'COMPLETED'
    GROUP BY
        merchant_id
),

merchant_kpis AS (
    SELECT
        dm.merchant_id,
        dm.merchant_name,
        dm.category,
        dm.city,
        dm.onboarded_date,
        COALESCE(ct.total_revenue, 0) AS total_revenue,
        COALESCE(ct.total_transactions, 0) AS total_transactions,
        COALESCE(ft.failed_count, 0) AS failed_count,
        COALESCE(ct.total_transactions, 0) + COALESCE(ft.failed_count, 0) AS total_attempts,
        COALESCE(ft.failed_count, 0) / NULLIF(COALESCE(ct.total_transactions, 0) + COALESCE(ft.failed_count, 0), 0) * 100 AS failure_rate_pct,
        COALESCE(atv.avg_transaction_value, 0) AS avg_transaction_value,
        COALESCE(uc.unique_customers, 0) AS unique_customers
    FROM
        SIGMA_DE.PUBLIC.dim_merchant dm
        LEFT JOIN completed_transactions ct ON dm.merchant_id = ct.merchant_id
        LEFT JOIN failed_transactions ft ON dm.merchant_id = ft.merchant_id
        LEFT JOIN avg_transaction_value atv ON dm.merchant_id = atv.merchant_id
        LEFT JOIN unique_customers uc ON dm.merchant_id = uc.merchant_id
)

SELECT
    *
FROM
    merchant_kpis
) select merchant_id
from __dbt__cte__mart_merchant_performance
where merchant_id is null


