-- daily_failure_rate.sql
-- Known bugs:
--   1. Correlated subquery — runs per group, extremely slow at scale
--   2. Cannot reference alias 'failed_count' in same SELECT — query will error
--   3. Integer division — gives 0 for any rate under 100%

SELECT transaction_date,
       (SELECT COUNT(*) FROM fact_transactions f2
        WHERE f2.status = 'FAILED'
        AND f2.transaction_date = t.transaction_date) as failed_count,
       COUNT(*) as total_count,
       failed_count / total_count * 100 as failure_rate
FROM fact_transactions t
GROUP BY transaction_date
ORDER BY transaction_date;
