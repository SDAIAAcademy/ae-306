<!-- academy:title -->
# Modern Data Engineering

هندسة البيانات الحديثة

AI Engineering Track · SDAIA Academy · AE-306 · Level 300

Build one batch pipeline from raw extracts to a tested, governed open table that two engines read

Participants build one batch pipeline end to end for Qafila, the fictional trading company of the Academy's data engineering course, whose margin report nobody trusts. They query raw extracts with analytical SQL, ingest an API and a database change feed incrementally, clean with dataframes, model a star schema with a slowly changing supplier dimension, write tested transformations and a data contract, orchestrate them, and land the result in an open table format that a second engine reads. Day four adds distributed processing, streaming and governance.

**Format:** Intensive: 4 teaching days of four sessions and a capstone day, with guided pre-work and a tracked follow-up task

**Course page:** https://sdaiaacademy.github.io/data-engineering/
<!-- /academy:title -->

## Outcomes

| | Outcomes | Level | Evidence |
|---|---|---|---|
| LO1 | Analyse raw transactional extracts with analytical SQL, including window functions and incremental predicates, given three months of synthetic orders, shipments and prices in columnar files | Applied | queries that reproduce the reference monthly margin and a note on two defects found |
| LO2 | Implement incremental ingestion from an API and a change feed, keeping supplier history as a slowly changing dimension, given a paginated API and a feed with updates and deletes | Applied | loads that add no duplicates on re-run and correct validity ranges |
| LO3 | Design a dimensional model at a stated grain and build it as tested, version-controlled transformations, given the finance team's five margin questions | Performance | a star schema, passing tests and a rebuild that skips unchanged models |
| LO4 | Build an orchestrated pipeline with a data contract, quality gates, retries and backfills that fails safely when an upstream feed breaks, given a supplier feed that changes its schema without notice | Performance | a run log showing the violation caught, the mart left unrefreshed and a backfill after the fix |
| LO5 | Configure an open table format with partitioning, schema evolution and time travel, and read it from a second engine, given the margin mart and one schema change | Applied | identical results from two engines and a query against an earlier snapshot |
| LO6 | Classify every field under the national classification levels and apply minimisation, masking and access rules, given the customer and supplier tables | Applied | a classification register and a masked view that passes access tests |

<!-- academy:units -->
## Units

| Unit | Title | Sessions | Slides |
|---|---|---|---|
| Day 1 | Store and query | Platform shapes; Analytical SQL on a single node; Window functions; Columnar files and partitioning | [`slides/day1.html`](slides/day1.html) |
| Day 2 | Ingest and clean | Ingesting from APIs; Declarative ingestion pipelines; Change data capture, merge and history; Cleaning with dataframes | [`slides/day2.html`](slides/day2.html) |
| Day 3 | Model and test | Dimensional modelling; Transformations as code; Data quality tests and contracts; Orchestration | [`slides/day3.html`](slides/day3.html) |
| Day 4 | Scale and production | Open table formats; Distributed processing when measured; Streaming fundamentals; Governance with PDPL and NDMO | [`slides/day4.html`](slides/day4.html) |
| Capstone | Capstone: the margin mart and its defence |  | [`slides/day5.html`](slides/day5.html) |
<!-- /academy:units -->

## Case study

**Qafila Trading** is a fictional importer and wholesaler of food and household goods in Jeddah, Riyadh and Dammam. It sells to 240 shops, restaurants and hotels and buys from 18 suppliers in five countries. Its finance controller does not trust the monthly margin report, and the course rebuilds it as one pipeline.

The sources are synthetic and generated with a fixed seed (`labs/qafila_data.py`): three months of order extracts, a paginated supplier price API, a supplier change feed and a shipment event stream. They are planted with the problems the labs find: cancelled orders still counted, lines re-sent by the order system, freight joined at the wrong grain, a supplier batch that breaks its contract, and a deleted customer who survives in history.

<!-- academy:labs -->
## Labs

Every lab is a notebook in `labs/`. Open it in Google Colab from the course page, or run it locally with `uv`. Exercises raise `NotImplementedError` until they are done; the reference versions are in `labs/solutions/`.

| | Session | Lab | File |
|---|---|---|---|
| 1.1 | Day 1 · Session 1 | Ten workloads, three layers | [`D1_1_platform_shapes.ipynb`](labs/D1_1_platform_shapes.ipynb) |
| 1.2 | Day 1 · Session 2 | Reproduce the monthly margin | [`D1_2_margin_sql.ipynb`](labs/D1_2_margin_sql.ipynb) |
| 1.3 | Day 1 · Session 3 | Running margin, price changes, first and last orders | [`D1_3_windows.ipynb`](labs/D1_3_windows.ipynb) |
| 1.4 | Day 1 · Session 4 | Partitioned columnar files, measured | [`D1_4_columnar.ipynb`](labs/D1_4_columnar.ipynb) |
| 2.1 | Day 2 · Session 1 | An incremental, idempotent API load | [`D2_1_api_ingestion.ipynb`](labs/D2_1_api_ingestion.ipynb) |
| 2.2 | Day 2 · Session 2 | The supplier load with dlt | [`D2_2_dlt_pipeline.ipynb`](labs/D2_2_dlt_pipeline.ipynb) |
| 2.3 | Day 2 · Session 3 | Supplier changes and their history | [`D2_3_cdc_scd.ipynb`](labs/D2_3_cdc_scd.ipynb) |
| 2.4 | Day 2 · Session 4 | Currencies, units and Arabic names | [`D2_4_cleaning.ipynb`](labs/D2_4_cleaning.ipynb) |
| 3.1 | Day 3 · Session 1 | The margin star schema | [`D3_1_star_schema.ipynb`](labs/D3_1_star_schema.ipynb) |
| 3.2 | Day 3 · Session 2 | Models, environments and a state-aware rebuild | [`D3_2_transformations.ipynb`](labs/D3_2_transformations.ipynb) |
| 3.3 | Day 3 · Session 3 | A contract that holds | [`D3_3_contracts.ipynb`](labs/D3_3_contracts.ipynb) |
| 3.4 | Day 3 · Session 4 | Assets, a failure, a retry and a backfill | [`D3_4_orchestration.ipynb`](labs/D3_4_orchestration.ipynb) |
| 4.1 | Day 4 · Session 1 | The mart as an Iceberg table | [`D4_1_table_format.ipynb`](labs/D4_1_table_format.ipynb) |
| 4.2 | Day 4 · Session 2 | One node or a local cluster | [`D4_2_distributed.ipynb`](labs/D4_2_distributed.ipynb) |
| 4.3 | Day 4 · Session 3 | Shipment events with a watermark | [`D4_3_streaming.ipynb`](labs/D4_3_streaming.ipynb) |
| 4.4 | Day 4 · Session 4 | Classification, masking and access tests | [`D4_4_governance.ipynb`](labs/D4_4_governance.ipynb) |
<!-- /academy:labs -->

Every lab starts from a supplied reference state (`Q.reference(...)` and `labs/data/`), so none depends on an earlier one. No lab needs a model, an API key, Docker or a cloud account: everything runs on a laptop CPU or on Google Colab. Set `DE_QUICK=1` for a smaller data set in class. See [`labs/README.md`](labs/README.md).

## Capstone

The margin mart from raw sources to an Apache Iceberg table, built on the Qafila capstone starter in [`labs/capstone/`](labs/capstone/README.md): incremental ingestion of the supplier API and the change feed with supplier history, a star schema at order-line grain, tested transformations and a data contract, an orchestrated run that blocks on a broken feed and backfills after the fix, and classification and masking of customer and supplier fields.

**Submission:** a public GitHub repository link. The assessor re-runs the pipeline from a clean checkout. The README reports row counts, test results and run times, and the commit history and run logs are in the repository. An eight-minute defence follows: one modelling decision, and one transformation the assessor selects.

| Criterion | Points |
|---|---|
| Correctness of the mart | 25 |
| Ingestion and history | 20 |
| Tests and contract | 20 |
| Orchestration and recovery | 15 |
| Table format and governance | 10 |
| Reproducibility | 10 |

## Prerequisites

- FN-102 Command Line, Git and Reproducible Projects
- FN-104 SQL and Data Wrangling
- Writes SQL joins, grouping and simple window functions
- Filters and joins tables with a Python dataframe library
- Commits with Git from a shell
- A laptop with [uv](https://docs.astral.sh/uv/), or Google Colab. Run `labs/00_setup_check.ipynb` before Day 1.

<!-- academy:tools -->
## Tools

Each line is a capability; the examples are interchangeable.

- **Single-node analytical engine and dataframes:** DuckDB, Polars
- **Ingestion:** dlt, plain Python with stored load state
- **Transformation framework with tests:** SQLMesh, dbt, plain SQL files with Pandera checks
- **Data contract specification:** Open Data Contract Standard, contract checks compiled to SQL tests
- **Orchestrator:** Dagster, Apache Airflow
- **Open table format and catalogue:** Apache Iceberg with a REST catalogue, Delta Lake, DuckLake
- **Distributed engine:** Apache Spark, Trino
- **Event streaming and lineage:** Apache Kafka, Apache Flink, OpenLineage
<!-- /academy:tools -->

The labs use DuckDB and Polars, dlt and plain Python, SQLMesh, the Open Data Contract Standard compiled to SQL checks, Dagster, Apache Iceberg through PyIceberg, and Dask in local mode in place of Spark or Trino, which would need Java or a cluster. A file-backed event log stands in for a Kafka broker.

<!-- academy:sources -->
## Sources

### National references

- [SDAIA: Data Classification Policy](https://sdaia.gov.sa/en/SDAIA/about/Documents/DataClassificationPolicy.pdf)
- [SDAIA: Personal Data Protection Law](https://sdaia.gov.sa/en/SDAIA/about/Documents/PersonalDataProtectionLaw.pdf)

### Modelling, change and contracts

- [Kimball Group: Type 2, add new row](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/)
- [Debezium: PostgreSQL connector, change event structure](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)
- [Bitol: Open Data Contract Standard (ODCS)](https://bitol-io.github.io/open-data-contract-standard/latest/)
- [Bitol: ODCS data quality](https://bitol-io.github.io/open-data-contract-standard/latest/data-quality/)

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
<!-- /academy:sources -->

### National references

- Personal Data Protection Law: https://sdaia.gov.sa/en/SDAIA/about/Documents/PersonalDataProtectionLaw.pdf
- Data Classification Policy: https://sdaia.gov.sa/en/SDAIA/about/Documents/DataClassificationPolicy.pdf
- NDMO Data Management and Personal Data Protection Standards: published by the National Data Management Office at https://sdaia.gov.sa/
