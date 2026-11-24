---
course: "Modern Data Engineering"
code: "AE-306"
version: "2027.2.0"
language: "en"
view: "trainee"
source: "https://sdaiaacademy.github.io/ae-306/index.html"
---

# Modern Data Engineering

هندسة البيانات الحديثة

AI Engineering Track · 4 teaching days + capstone day · 26 hours · Level 300

Build one batch pipeline from raw extracts to a tested, governed open table that two engines read

Participants build one batch pipeline end to end for Qafila, the fictional trading company of the Academy's data engineering course, whose margin report nobody trusts. They query raw extracts with analytical SQL, ingest an API and a database change feed incrementally, clean with dataframes, model a star schema with a slowly changing supplier dimension, write tested transformations and a data contract, orchestrate them, and land the result in an open table format that a second engine reads. Day four adds distributed processing, streaming and governance.

**Who it is for:** Practitioners: engineers and analysts who already write SQL and work with Python dataframes, and who now need a batch pipeline that is incremental, tested, held by a contract and governed.

**Format:** Intensive: 4 teaching days of four sessions and a capstone day, with guided pre-work and a tracked follow-up task

## The case study

**Qafila Trading.** Qafila Trading is a fictional importer and wholesaler of food and household goods in Jeddah, Riyadh and Dammam, selling to 240 shops, restaurants and hotels and buying from 18 suppliers in five countries. Its finance controller, Lujain Al-Zamil, does not trust the monthly margin report. Participants rebuild it as one pipeline: order extracts, a paginated supplier price API, a supplier change feed and a shipment event stream, all synthetic, generated with a fixed seed and planted with the problems the labs find.

## The course

### Day 1: Store and query

Slides: https://sdaiaacademy.github.io/ae-306/slides/day1.md

- **Session 1: Platform shapes**
  - Tell a transactional workload from an analytical one by its access pattern
  - Measure a point lookup and an aggregate on a row store and a column store
  - Place a workload in a layer and justify it in one sentence
  - [Lab 1.1: Ten workloads, three layers (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D1_1_platform_shapes.ipynb)
- **Session 2: Analytical SQL on a single node**
  - Query CSV and JSON files in place with DuckDB
  - Join lines to a price list valid on the order date
  - Reproduce a reference figure and explain each difference
  - [Lab 1.2: Reproduce the monthly margin (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D1_2_margin_sql.ipynb)
- **Session 3: Window functions**
  - Write a running total with a window frame
  - Detect changes with LAG over an ordered partition
  - Keep one row per group with ROW_NUMBER and QUALIFY
  - [Lab 1.3: Running margin, price changes, first and last orders (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D1_3_windows.ipynb)
- **Session 4: Columnar files and partitioning**
  - Convert row files to Parquet and compare size and scan time
  - Read row-group statistics and see which groups a filter skips
  - Partition by month and measure what a one-month query reads
  - [Lab 1.4: Partitioned columnar files, measured (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D1_4_columnar.ipynb)

### Day 2: Ingest and clean

Slides: https://sdaiaacademy.github.io/ae-306/slides/day2.md

- **Session 1: Ingesting from APIs**
  - Follow every page of a cursor-paginated API
  - Back off on 429 responses
  - Store load state with the data so a re-run adds nothing
  - [Lab 2.1: An incremental, idempotent API load (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D2_1_api_ingestion.ipynb)
- **Session 2: Declarative ingestion pipelines**
  - Declare a REST resource with an incremental cursor and a primary key
  - Absorb a new source column and find it in the schema
  - Read a pipeline's load state and load history
  - [Lab 2.2: The supplier load with dlt (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D2_2_dlt_pipeline.ipynb)
- **Session 3: Change data capture, merge and history**
  - Read a change event envelope and order events by log position
  - Apply updates and deletes to a copy with MERGE
  - Keep history as a type 2 dimension with valid ranges
  - [Lab 2.3: Supplier changes and their history (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D2_3_cdc_scd.ipynb)
- **Session 4: Cleaning with dataframes**
  - Write cleaning steps as Polars expressions
  - Convert currencies and units to one cost per piece in SAR
  - Normalise Arabic names and log every rule with the rows it changed
  - [Lab 2.4: Currencies, units and Arabic names (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D2_4_cleaning.ipynb)

### Day 3: Model and test

Slides: https://sdaiaacademy.github.io/ae-306/slides/day3.md

- **Session 1: Dimensional modelling**
  - State the grain of a fact table in one sentence and test it
  - Build dimensions with an unknown member and a type 2 supplier
  - Find and fix a fan-out before it reaches a report
  - [Lab 3.1: The margin star schema (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D3_1_star_schema.ipynb)
- **Session 2: Transformations as code**
  - Write staging and mart models as SQL files under version control
  - Plan a change in a development environment before production
  - Show that a rebuild skips unchanged models
  - [Lab 3.2: Models, environments and a state-aware rebuild (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D3_2_transformations.ipynb)
- **Session 3: Data quality tests and contracts**
  - Write not-null, unique, accepted-value and relationship tests
  - Write a data contract for a feed and compile it to SQL checks
  - Block a refresh when the contract fails, and say why
  - [Lab 3.3: A contract that holds (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D3_3_contracts.ipynb)
- **Session 4: Orchestration**
  - Declare the pipeline as assets with dependencies and monthly partitions
  - Retry a flaky source and block on a failed check
  - Backfill one month after a fix
  - [Lab 3.4: Assets, a failure, a retry and a backfill (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D3_4_orchestration.ipynb)

### Day 4: Scale and production

Slides: https://sdaiaacademy.github.io/ae-306/slides/day4.md

- **Session 1: Open table formats**
  - Write a table in an open format with a partition spec
  - Evolve its schema without rewriting data
  - Query an earlier snapshot from a second engine
  - [Lab 4.1: The mart as an Iceberg table (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D4_1_table_format.ipynb)
- **Session 2: Distributed processing when measured**
  - Explain partitions, shuffles and stages in a distributed engine
  - Run the same transformation on a local cluster and a single node
  - Decide from measured time and memory, not from habit
  - [Lab 4.2: One node or a local cluster (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D4_2_distributed.ipynb)
- **Session 3: Streaming fundamentals**
  - Consume a log by offset and commit progress
  - Make a consumer idempotent under at-least-once delivery
  - Window by event time with a watermark and reconcile with batch
  - [Lab 4.3: Shipment events with a watermark (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D4_3_streaming.ipynb)
- **Session 4: Governance with PDPL and NDMO**
  - Classify every field under the national classification levels
  - Drop what the report does not need and mask the rest per role
  - Test that a role cannot read what it must not
  - [Lab 4.4: Classification, masking and access tests (25 min)](https://sdaiaacademy.github.io/ae-306/labs/D4_4_governance.ipynb)

### Capstone: Capstone: the margin mart and its defence

Slides: https://sdaiaacademy.github.io/ae-306/slides/day5.md

## Capstone

The margin mart from raw sources to an Apache Iceberg table, built on the course's Qafila capstone starter (labs/capstone/): incremental ingestion of the supplier API and the change feed with supplier history, a star schema at order-line grain, tested transformations and a data contract, an orchestrated run that blocks on a broken feed and backfills after the fix, and classification and masking of customer and supplier fields.

**What you submit:** A public GitHub repository link. The assessor re-runs the pipeline from a clean checkout; the README reports row counts, test results and run times, and the commit history and run logs are in the repository. Then an eight-minute defence of one modelling decision, in which the participant also explains one transformation the assessor selects.

**Rubric:**

- Correctness of the mart: 25%
- Ingestion and history: 20%
- Tests and contract: 20%
- Orchestration and recovery: 15%
- Table format and governance: 10%
- Reproducibility: 10%

## Outcomes

- **LO1** Analyse raw transactional extracts with analytical SQL, including window functions and incremental predicates, given three months of synthetic orders, shipments and prices in columnar files (Applied) Evidence: queries that reproduce the reference monthly margin and a note on two defects found
- **LO2** Implement incremental ingestion from an API and a change feed, keeping supplier history as a slowly changing dimension, given a paginated API and a feed with updates and deletes (Applied) Evidence: loads that add no duplicates on re-run and correct validity ranges
- **LO3** Design a dimensional model at a stated grain and build it as tested, version-controlled transformations, given the finance team's five margin questions (Performance) Evidence: a star schema, passing tests and a rebuild that skips unchanged models
- **LO4** Build an orchestrated pipeline with a data contract, quality gates, retries and backfills that fails safely when an upstream feed breaks, given a supplier feed that changes its schema without notice (Performance) Evidence: a run log showing the violation caught, the mart left unrefreshed and a backfill after the fix
- **LO5** Configure an open table format with partitioning, schema evolution and time travel, and read it from a second engine, given the margin mart and one schema change (Applied) Evidence: identical results from two engines and a query against an earlier snapshot
- **LO6** Classify every field under the national classification levels and apply minimisation, masking and access rules, given the customer and supplier tables (Applied) Evidence: a classification register and a masked view that passes access tests

## Tools

- **Single-node analytical engine and dataframes:** DuckDB, Polars
- **Ingestion:** dlt, plain Python with stored load state
- **Transformation framework with tests:** SQLMesh, dbt, plain SQL files with Pandera checks
- **Data contract specification:** Open Data Contract Standard, contract checks compiled to SQL tests
- **Orchestrator:** Dagster, Apache Airflow
- **Open table format and catalogue:** Apache Iceberg with a REST catalogue, Delta Lake, DuckLake
- **Distributed engine:** Apache Spark, Trino
- **Event streaming and lineage:** Apache Kafka, Apache Flink, OpenLineage

## Prerequisites

- FN-102 Command Line, Git and Reproducible Projects
- FN-104 SQL and Data Wrangling
- Writes SQL joins, grouping and simple window functions
- Filters and joins tables with a Python dataframe library
- Commits with Git from a shell
- Setup: a laptop CPU with uv, or Google Colab. No model, no key, no Docker, no cloud account. Run 00_setup_check before Day 1; see labs/README.md.

## Sources

### National references

- [SDAIA: Data Classification Policy](https://sdaia.gov.sa/en/SDAIA/about/Documents/DataClassificationPolicy.pdf)
- [SDAIA: Personal Data Protection Law](https://sdaia.gov.sa/en/SDAIA/about/Documents/PersonalDataProtectionLaw.pdf)

### Modelling, change and contracts

- [Kimball Group: Type 2, add new row](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/)
- [Debezium: PostgreSQL connector, change event structure](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)
- [Bitol: Open Data Contract Standard (ODCS)](https://bitol-io.github.io/open-data-contract-standard/latest/)
- [Bitol: ODCS data quality](https://bitol-io.github.io/open-data-contract-standard/latest/data-quality/)
- [Danilo Sato: Parallel Change (martinfowler.com)](https://martinfowler.com/bliki/ParallelChange.html)

### Files and table formats

- [Apache Parquet: file format](https://parquet.apache.org/docs/file-format/)
- [Apache Iceberg: table specification](https://iceberg.apache.org/spec/)
- [PyIceberg documentation](https://py.iceberg.apache.org/)

### Tools used in the labs

- [DuckDB documentation](https://duckdb.org/docs/)
- [Polars documentation](https://docs.pola.rs/)
- [dlt documentation](https://dlthub.com/docs/intro)
- [SQLMesh documentation](https://sqlmesh.readthedocs.io/en/stable/)
- [Dagster documentation](https://docs.dagster.io/)
- [Dask documentation](https://docs.dask.org/en/stable/)

---

SDAIA Academy · AI Engineering Track · Modern Data Engineering

Course version 2027.2.0 · engine 1.0.0 · built 2026-11-24 · commit b55d5bf
