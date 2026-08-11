# Pipeline Design Document

## What This Pipeline Does
This pipeline ingests transaction data, cleans and enriches it, and then aggregates it into merchant performance metrics and daily summaries.

## Data Flow Diagram

```
+--------------------+      +--------------------+      +--------------------+      +--------------------+
|  Source            |      |  Bronze Layer      |      |  Silver Layer      |      |  Gold Layer        |
|  (TRANSACTIONS)    | ---> |  (bronze_transactions) | ---> |  (silver_transactions) | ---> |  (gold_merchant_performance, |
|                    |      |                    |      |                    |      |  gold_daily_summary) |
+--------------------+      +--------------------+      +--------------------+      +--------------------+
```

## Key Design Decisions
- **Layered Approach**: The pipeline uses a three-layer approach (Bronze, Silver, Gold) to ensure data quality and enrichment before aggregation.
- **Quality Flags**: Introduced quality flags in the Silver layer to identify and handle dirty data.
- **Aggregative Metrics**: Computed merchant performance and daily summaries in the Gold layer to provide actionable insights.
- **Date-Partitioning**: Gold layer tables are partitioned by date to facilitate time-based queries and reporting.

## Known Limitations
- **Data Consistency**: The pipeline assumes that the source data is consistent and does not handle schema changes.
- **Error Handling**: Limited error handling in the transformation and loading steps, which could lead to data loss.
- **Performance**: The pipeline is not optimized for large datasets and may experience performance issues.
- **Data Freshness**: The pipeline runs once per day, which may not meet real-time data needs.

## Dependencies
- **DuckDB**: The pipeline relies on DuckDB for data storage and querying.
- **MERCHANTS**: A list of merchant details required for enriching transaction data.
- **TRANSACTIONS_CLEAN and TRANSACTIONS_DIRTY**: Source transaction data, both clean and dirty.
- **AWS S3**: Used for storing and retrieving the pipeline configuration and data (not explicitly shown in the code).