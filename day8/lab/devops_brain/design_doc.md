# Pipeline Design Document

## What This Pipeline Does

This pipeline ingests transaction data from both clean and dirty sources, enriches it with merchant details, and processes it into three layers: Bronze, Silver, and Gold. The Bronze layer stores raw transactions, the Silver layer stores enriched transactions, and the Gold layer stores aggregated merchant performance and daily summaries.

## Data Flow Diagram

```
+----------------+     +--------------------+     +--------------------+     +--------------------+     +--------------------+
|  Source       |     |  Bronze Layer      |     |  Silver Layer      |     |  Gold Layer        |     |  Gold Layer        |
|  (Clean/Dirty) | --> |  bronze_transactions | --> |  silver_transactions | --> |  gold_merchant_performance | --> |  gold_daily_summary |
+----------------+     +--------------------+     +--------------------+     +--------------------+     +--------------------+
```

## Key Design Decisions

- **Layered Approach**: The pipeline uses a Bronze-Silver-Gold approach to separate raw data ingestion, data enrichment, and aggregation.
- **Quality Flags**: Transactions are flagged as 'CLEAN' or 'FAILED' to distinguish between successful and failed transactions.
- **Merchant Enrichment**: Merchant details are joined with transactions during the transformation to Silver to enrich the data.
- **Aggregation**: Aggregations are computed at the Gold layer to provide insights into merchant performance and daily summaries.

## Known Limitations

- **Single Source**: The pipeline currently supports only one source of transactions. Adding more sources would require modifications.
- **No Error Handling**: The pipeline does not handle errors during data ingestion or transformation, leading to potential data loss.
- **Static Merchant Data**: Merchant data is loaded once and not updated unless the pipeline is rerun, which may not reflect real-time changes.
- **Limited Transformations**: The pipeline performs basic transformations and does not support complex data manipulations.

## Dependencies

- **DuckDB**: The pipeline relies on DuckDB for data storage and querying.
- **MERCHANTS**: A list of merchant details used for enriching transactions.
- **TRANSACTIONS_CLEAN and TRANSACTIONS_DIRTY**: The source data files containing transaction records.