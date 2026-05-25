-- models/staging/stg_fact_transactions.sql

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
        {{ source('sigma_analytics', 'fact_transactions') }}
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
```

```yaml
# models/staging/schema.yml

version: 2

models:
  - name: stg_fact_transactions
    description: "Staging model for fact_transactions. Cleans and prepares data for further transformation."
    columns:
      - name: transaction_id
        description: "Unique identifier for each transaction."
        tests:
          - not_null
          - unique
      - name: amount
        description: "Amount of the transaction in USD."
        tests:
          - not_null
      - name: status
        description: "Status of the transaction (COMPLETED, FAILED, PENDING)."
        tests:
          - not_null
          - accepted_values:
              values: ["COMPLETED", "FAILED", "PENDING"]
      - name: merchant_id
        description: "Foreign key referencing dim_merchant."
        tests:
          - not_null
      - name: customer_id
        description: "Foreign key referencing dim_customer."
        tests:
          - not_null
      - name: transaction_date
        description: "Date of the transaction."
        tests:
          - not_null
      - name: payment_method
        description: "Payment method used for the transaction (CREDIT_CARD, DEBIT_CARD, UPI)."
        tests:
          - not_null
          - accepted_values:
              values: ["CREDIT_CARD", "DEBIT_CARD", "UPI"]
      - name: loaded_at
        description: "Timestamp when the data was loaded into the staging table."
        tests:
          - not_null
