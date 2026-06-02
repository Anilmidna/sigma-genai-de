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
    WHERE 
        merchant_id NOT LIKE 'TEST_%'
),

cleaned_transactions AS (
    SELECT 
        LOWER(transaction_id) AS transaction_id,
        CAST(amount AS DECIMAL(10,2)) AS amount,
        LOWER(status) AS status,
        LOWER(merchant_id) AS merchant_id,
        LOWER(customer_id) AS customer_id,
        CAST(transaction_date AS DATE) AS transaction_date,
        LOWER(payment_method) AS payment_method,
        CURRENT_TIMESTAMP AS loaded_at
    FROM 
        raw_transactions
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
        description: "Status of the transaction. Possible values: completed, failed, pending."
        tests:
          - not_null
          - accepted_values:
              values: ['completed', 'failed', 'pending']
      - name: merchant_id
        description: "Unique identifier for the merchant associated with the transaction."
        tests:
          - not_null
      - name: customer_id
        description: "Unique identifier for the customer associated with the transaction."
        tests:
          - not_null
      - name: transaction_date
        description: "Date on which the transaction occurred."
        tests:
          - not_null
      - name: payment_method
        description: "Payment method used for the transaction. Possible values: credit_card, debit_card, upi."
        tests:
          - not_null
          - accepted_values:
              values: ['credit_card', 'debit_card', 'upi']
      - name: loaded_at
        description: "Timestamp when the data was loaded into the staging table."
        tests:
          - not_null
