# hackernews_api.db

A production-grade data engineering pipeline designed to ingest real-time metadata streams from the public Hacker News API, isolate unique external destination domains, evaluate their availability via network requests, and serve the resulting performance metrics through an analytical dashboard layer.

## System Architecture

                  +----------------------+
                  |   Hacker News API    |
                  +----------+-----------+
                             |
                             v Ingestion (main.py)
                  +----------------------+
                  |  Domain Extraction   |
                  |   & Latency Checks   |
                  +----------+-----------+
                             |
                             v Serverless Transaction Layer
                  +----------------------+
                  |  DuckDB Data Lake    |
                  |  (web_decay_dw.db)   |
                  +----------+-----------+
                             |
                             v Presentation Layer
                  +----------------------+
                  | Streamlit Dashboard  |
                  |   (dasboard.py)      |
                  +----------------------+

The infrastructure runs entirely serverless, leveraging an embedded DuckDB database file for high-performance relational storage. The data warehouse is structured using a normalized Star Schema to separate core network event measurements from descriptive dimensions.

## Data Warehouse Schema

The database consists of seven interconnected tables configured to track pipeline execution metrics, user alerting boundaries, and domain reputation shifts over time.

* sys_pipeline_log: Contains metadata logs for every individual pipeline execution to ensure system auditability and lineage tracking.
* dim_hackernews_item: Stores properties of the source posts, including upvote scores and comment counts to gauge link exposure.
* dim_domain: Holds unique master web domains, top-level extensions, and blocklist indicators to prevent text deduplication.
* dim_domain_history: Implements Slowly Changing Dimension (SCD Type 2) tracking to record shifts in domain reliability over time without losing historical context.
* dim_user: Stores subscriber notification preferences and communication endpoints.
* fact_link_status: The central operational metrics log containing latency measurements, HTTP codes, and failure flags mapped back to individual system log contexts.
* fact_alerts: Documents downstream system notification dispatches triggered by identified link decay events.

## Key Engineering Solutions

* Network Optimization: Implements high-speed HTTP HEAD requests rather than full GET payloads, bypassing webpage body compilation to cut checking latencies by over ninety percent.
* Deterministic Token Hashing: Utilizes localized SHA-256 cryptographic algorithms on domain strings, guaranteeing uniform lookup keys and saving warehouse storage capacity.
* Idempotence and Transaction Handling: Uses transactional table upserts (ON CONFLICT) to prevent pipeline execution overlap from corrupting historical metadata or creating duplicate key anomalies.

## File Structure

├── main.py        # Connects to the public API, parses URLs, and pings host servers.
├── database.py    # Manages schema configurations, table indexes, and transaction writes.
└── dasboard.py    # Queries DuckDB and renders interactive layout charts in the browser.

## Setup and Execution

1. Environment Installation
Install the necessary system components via python package management:
pip install duckdb streamlit plotly pandas requests

2. Run Ingestion Pipeline
Execute the main script to initialize the local data warehouse file, fetch the live feed, and run network latency audits:
python main.py

3. Launch Presentation Analytics
Boot the presentation web application to review your live tracking metrics:
streamlit run python_files/dasboard.py
