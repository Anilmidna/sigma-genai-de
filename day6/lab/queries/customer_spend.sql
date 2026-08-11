-- customer_spend.sql
-- Known bugs:
--   1. LEFT JOIN + WHERE on right table = effective INNER JOIN (drops 0-order customers)
--   2. GROUP BY missing c.tier — will fail in Snowflake/PostgreSQL
--   3. Selecting email — PII exposure risk
--   4. No date filter — causes full table scan on large data

SELECT c.customer_name, c.email, c.tier,
       SUM(t.amount) as lifetime_value,
       COUNT(t.transaction_id) as total_orders
FROM dim_customer c
LEFT JOIN fact_transactions t ON c.customer_id = t.customer_id
WHERE t.status = 'COMPLETED'
GROUP BY c.customer_name, c.email
HAVING SUM(t.amount) > 1000
ORDER BY lifetime_value DESC;
