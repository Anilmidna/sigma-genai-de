# Pipeline Design Document

## What This Pipeline Does
This pipeline ingests transaction data from both clean and dirty sources, processes it, and stores it in three layers: Bronze, Silver, and Gold. The Bronze layer stores raw transactions, the Silver layer stores enriched transactions with merchant details, and the Gold layer stores aggregated merchant performance and daily summaries.

## Data Flow Diagram
```plaintext
SOURCE
    |
    v
BRONZE_TRANSACTIONS
    |
    v
TRANSFORM (Clean, Enrich)
    |
    v
SILVER_TRANSACTIONS
    |
    v
AGGREGATE (Merchant Performance, Daily Summary)
    |
    v
GOLD_MERCHANT_PERFORMANCE
    |
    v
GOLD_DAILY_SUMMARY
```

## Key Design Decisions
- **Layered Storage**: The pipeline uses a three-tier storage approach to ensure data integrity and ease of access at different stages of processing.
- **Enrichment in Silver Layer**: Merchant details are added in the Silver layer to ensure that all transactions have enriched data before aggregation.
- **Aggregation in Gold Layer**: Aggregations are performed in the Gold layer to provide high-level metrics and summaries, keeping the raw and enriched data separate.
- **Use of DuckDB**: DuckDB is chosen for its speed and ease of use for analytical queries, suitable for both development and production environments.

## Known Limitations
- **Single Source**: The pipeline currently only processes data from predefined clean and dirty sources, without support for dynamic data sources.
- **Static Merchant Data**: Merchant data is loaded once at the start and not updated dynamically, which could lead to stale merchant information.
- **Limited Error Handling**: The pipeline has basic error handling, which may not cover all edge cases and could lead to data inconsistencies.
- **No Data Validation**: There is no comprehensive data validation step, which could result in incorrect data being processed.

## Dependencies
- **DuckDB**: The pipeline relies on DuckDB for database operations.
- **MERCHANTS**: A predefined list of merchants used for enriching transaction data.
- **TRANSACTIONS_CLEAN and TRANSACTIONS_DIRTY**: Source data files containing clean and dirty transactions, respectively.