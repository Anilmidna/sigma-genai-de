WITH filtered_transactions AS (
    SELECT
        transaction_id,
        amount,
        status,
        merchant_id,
        customer_id,
        transaction_date,
        payment_method
    FROM
        {{ ref('stg_fact_transactions') }}
    WHERE
        status IN ('COMPLETED', 'FAILED')
),

merchant_details AS (
    SELECT
        merchant_id,
        merchant_name,
        category,
        city,
        onboarded_date
    FROM
        {{ ref('dim_merchant') }}
),

aggregated_metrics AS (
    SELECT
        ft.merchant_id,
        COUNT(ft.transaction_id) AS total_transactions,
        COUNT(CASE WHEN ft.status = 'FAILED' THEN 1 END) AS failed_count,
        SUM(CASE WHEN ft.status = 'COMPLETED' THEN ft.amount ELSE 0 END) AS total_revenue,
        COUNT(DISTINCT ft.customer_id) AS unique_customers,
        AVG(CASE WHEN ft.status = 'COMPLETED' THEN ft.amount ELSE NULL END) AS avg_transaction_value
    FROM
        filtered_transactions ft
    GROUP BY
        ft.merchant_id
)

SELECT
    md.merchant_id,
    md.merchant_name,
    md.category,
    md.city,
    md.onboarded_date,
    am.total_transactions,
    am.failed_count,
    am.total_revenue,
    (am.failed_count::DECIMAL / NULLIF(am.total_transactions, 0)) * 100 AS failure_rate_pct,
    am.avg_transaction_value,
    am.unique_customers
FROM
    merchant_details md
JOIN
    aggregated_metrics am ON md.merchant_id = am.merchant_id
