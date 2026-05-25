WITH cleaned_transactions AS (
    SELECT
        LOWER(transaction_id) AS transaction_id,
        CAST(amount AS DECIMAL(10, 2)) AS amount,
        LOWER(status) AS status,
        LOWER(merchant_id) AS merchant_id,
        LOWER(customer_id) AS customer_id,
        CAST(transaction_date AS DATE) AS transaction_date,
        LOWER(payment_method) AS payment_method,
        CURRENT_TIMESTAMP AS loaded_at
    FROM
        {{ source('sigma_analytics', 'fact_transactions') }}
    WHERE
        merchant_id NOT LIKE 'TEST_%'
)

SELECT * FROM cleaned_transactions
```

```yaml
version: 2

models:
  - name: stg_fact_transactions
    description: "Staging model for fact_transactions table. Cleans and prepares data for further transformation."
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
              values: ['completed', 'failed', 'pending']
      - name: merchant_id
        description: "Unique identifier for the merchant."
        tests:
          - not_null
      - name: customer_id
        description: "Unique identifier for the customer."
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
              values: ['credit_card', 'debit_card', 'upi']
      - name: loaded_at
        description: "Timestamp when the data was loaded."
        tests:
          - not_null
