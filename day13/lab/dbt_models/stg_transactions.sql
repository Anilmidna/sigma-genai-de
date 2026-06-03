-- stg_transactions.sql
-- Staging: raw transaction events from S3 Bronze layer

{{ config(materialized='view') }}

SELECT
    transaction_id,
    customer_id,
    merchant_id,
    amount,
    currency,
    payment_method,
    transaction_date,
    transaction_status,
    failure_reason,
    device_id,
    ip_address,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'transactions') }}
WHERE transaction_id IS NOT NULL
  AND amount > 0
