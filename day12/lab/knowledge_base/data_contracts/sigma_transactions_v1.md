# Data Contract — sigma-transactions stream v1
**Owner:** Platform Engineering
**Consumers:** Snowflake SILVER.TRANSACTIONS, Databricks Bronze layer
**Version:** 1.0 | Effective: 18 May 2026

## Schema

| Field | Type | Required | Notes |
|---|---|---|---|
| transaction_id | STRING | YES | Primary key. Format: TXN followed by 9 digits. |
| merchant_name | STRING | YES | Full merchant name. NOT abbreviated. |
| category | STRING | YES | One of: retail, fuel, food, electronics, pharmacy, grocery, pet, automotive, travel, tech |
| amount | DOUBLE | YES | Positive number. INR unless currency field specifies otherwise. |
| currency | STRING | YES | One of: INR, USD, EUR, GBP |
| transaction_date | DATE | YES | Format: YYYY-MM-DD. NOT DD-MM-YYYY. |
| status | STRING | YES | One of: completed, pending, failed |
| customer_id | STRING | YES | Format: C followed by 4 digits |
| payment_method | STRING | YES | One of: UPI, card, netbanking, wallet |
| merchant_city | STRING | YES | City name, no abbreviation |

## Breaking Changes

Any change to this schema is a BREAKING CHANGE and requires:
1. A data contract version bump (v1 → v2)
2. Approval from the Platform Engineering lead
3. A migration plan for all consumers
4. 2 weeks notice to all consuming teams

## Known Bad Patterns (from past incidents)

- Lambda v2 (deployed 2026-06-04 02:11 UTC): renamed `merchant_name` to `merchant_nm`
  and changed date format to DD-MM-YYYY. Caused 7-hour silent failure.
  Lesson: field renames are breaking changes even if data is still present.

- Firehose buffer flush (2026-05-22): partial JSON records in S3.
  Lesson: monitor Firehose DeliveryToS3.DataFreshness, not just errors.
