-- revenue_by_merchant.sql
-- Known bugs:
--   1. Implicit JOIN (FROM a, b WHERE) — performance anti-pattern
--   2. No STATUS='COMPLETED' filter — includes FAILED in revenue
--   3. ORDER BY ascending — should be DESC for 'top 10'

SELECT m.merchant_name,
       SUM(t.amount) as total_revenue,
       COUNT(*) as txn_count
FROM fact_transactions t, dim_merchant m
WHERE t.merchant_id = m.merchant_id
AND t.transaction_date > '2024-01-01'
GROUP BY m.merchant_name
ORDER BY total_revenue
LIMIT 10;
