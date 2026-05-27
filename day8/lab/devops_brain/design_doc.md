# Pipeline Technical Design Document

## What This Pipeline Does
This pipeline ingests transaction data, enriches it with merchant information, and then transforms it into clean, enriched, and aggregated formats for analytical purposes.

## Data Flow Diagram

```plaintext
Source (TRANSACTIONS_CLEAN, TRANSACTIONS_DIRTY) →
Bronze (bronze_transactions) →
Silver (silver_transactions) →
Gold (gold_merchant_performance, gold_daily_summary)
```

## Key Design Decisions
- **Layered Data Processing:** The pipeline uses a three-layer approach (Bronze, Silver, Gold) to ensure data is progressively cleaned and enriched before being used for analytics.
- **Data Quality Flags:** The Silver layer includes a quality flag to distinguish between clean and dirty data, enabling better data quality control.
- **Aggregation at Gold Layer:** The Gold layer performs aggregations and summaries, making it easier to perform analytics without repeatedly processing raw data.
- **Use of DuckDB:** DuckDB is chosen for its performance and ease of use, especially for analytical queries on large datasets.

## Known Limitations
- **Single Source of Transactions:** The pipeline currently only processes data from `TRANSACTIONS_CLEAN` and `TRANSACTIONS_DIRTY`. Adding more sources would require modifications.
- **Static Merchant Data:** Merchants data is loaded once and not updated in real-time, which may lead to stale merchant information.
- **No Error Handling in Data Loads:** The pipeline lacks robust error handling in data loading steps, which could lead to data loss if an error occurs.
- **Limited Concurrency:** The pipeline runs sequentially, which may not be optimal for very large datasets.

## Dependencies
- **DuckDB Database:** The pipeline relies on DuckDB for storing and querying data.
- **MERCHANTS Data:** A list of merchants with their details is required for enriching transaction data.
- **TRANSACTIONS_CLEAN and TRANSACTIONS_DIRTY:** These are the primary data sources for the pipeline.