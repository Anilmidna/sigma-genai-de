-- Deliberate failing test for cancelled status
-- We flip the logic so that it returns rows, forcing dbt to register a test failure
SELECT *
FROM {{ ref('stg_transactions') }}
-- Return all rows that are NOT cancelled (which is all of them) so the test fails
WHERE status != 'CANCELLED'
