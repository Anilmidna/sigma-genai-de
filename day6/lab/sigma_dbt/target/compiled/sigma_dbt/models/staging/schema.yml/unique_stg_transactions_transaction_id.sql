
    
    

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
) select
    transaction_id as unique_field,
    count(*) as n_records

from __dbt__cte__stg_transactions
where transaction_id is not null
group by transaction_id
having count(*) > 1


