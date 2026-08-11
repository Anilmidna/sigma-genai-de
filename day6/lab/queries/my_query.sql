-- Merchant Performance Dashboard Query
-- Purpose: Show top merchants by revenue with customer and failure stats

SELECT
    m.merchant_name,
    m.category,
    m.city,
    SUM(t.amount) AS total_revenue,

    COUNT(t.transaction_id) AS total_txns,

    (SELECT COUNT(*)
     FROM fact_transactions f2
     WHERE f2.merchant_id = m.merchant_id
       AND f2.status = 'FAILED') AS failed_cnt,

    ROUND(
        100.0 * (SELECT COUNT(*) FROM fact_transactions f3
                 WHERE f3.merchant_id = m.merchant_id
                   AND f3.status = 'FAILED')
        / NULLIF(COUNT(t.transaction_id), 0)
    , 2) AS failure_rate_pct,

    c.customer_name,
    c.email,

    SUM(t.amount) / COUNT(t.transaction_id) AS a

FROM fact_transactions t, dim_merchant m,
     dim_customer c

WHERE t.merchant_id = m.merchant_id
  AND t.customer_id = c.customer_id

GROUP BY m.merchant_name, m.category, m.city,
         c.customer_name, c.email

ORDER BY total_revenue ASC;