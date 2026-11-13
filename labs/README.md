# Modern Data Engineering: labs

Hands-on notebooks for the SDAIA Academy course **AE-306 Modern Data Engineering (هندسة البيانات الحديثة)**. Every lab
rebuilds a piece of the margin report of **Qafila Trading**, a fictional importer and wholesaler of food and household
goods in Jeddah, Riyadh and Dammam. Each lab starts from a supplied reference state, so none depends on an earlier one.

No lab uses a model, an API key, Docker or a cloud account. A laptop CPU or a Colab CPU runtime is enough.

## Quick start

**Google Colab**
1. Open a notebook from the [course page](https://sdaiaacademy.github.io/data-engineering/), or directly:
   `https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/<notebook>.ipynb`.
2. Run the first cell. It clones this repository and installs `requirements-colab.txt`.

**Local**
```bash
git clone https://github.com/SDAIAAcademy/data-engineering
cd data-engineering/labs
uv sync                        # creates .venv from pyproject.toml (uv.lock pins every version)
uv run jupyter lab
```
Run `00_setup_check.ipynb` once before Day 1. It checks the packages, the data and a smoke test of the tools.

**Quick mode.** `DE_QUICK=1` makes the timing labs (1.1, 1.4, 4.2) use fewer rows, so they finish in class time.
Every answer the labs check stays the same.

## Notebooks

| Day | Session | Notebook |
|---|---|---|
| 0 | Setup | [`00_setup_check.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/00_setup_check.ipynb) |
| 1 | Ten workloads, three layers | [`D1_1_platform_shapes.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D1_1_platform_shapes.ipynb) |
| 1 | Reproduce the monthly margin (AI-off) | [`D1_2_margin_sql.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D1_2_margin_sql.ipynb) |
| 1 | Running margin, price changes, first and last orders | [`D1_3_windows.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D1_3_windows.ipynb) |
| 1 | Partitioned columnar files, measured | [`D1_4_columnar.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D1_4_columnar.ipynb) |
| 2 | An incremental, idempotent API load | [`D2_1_api_ingestion.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D2_1_api_ingestion.ipynb) |
| 2 | The supplier load with dlt | [`D2_2_dlt_pipeline.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D2_2_dlt_pipeline.ipynb) |
| 2 | Supplier changes and their history | [`D2_3_cdc_scd.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D2_3_cdc_scd.ipynb) |
| 2 | Currencies, units and Arabic names | [`D2_4_cleaning.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D2_4_cleaning.ipynb) |
| 3 | The margin star schema | [`D3_1_star_schema.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D3_1_star_schema.ipynb) |
| 3 | Models, environments and a state-aware rebuild | [`D3_2_transformations.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D3_2_transformations.ipynb) |
| 3 | A contract that holds | [`D3_3_contracts.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D3_3_contracts.ipynb) |
| 3 | Assets, a failure, a retry and a backfill | [`D3_4_orchestration.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D3_4_orchestration.ipynb) |
| 4 | The mart as an Iceberg table | [`D4_1_table_format.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D4_1_table_format.ipynb) |
| 4 | One node or a local cluster | [`D4_2_distributed.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D4_2_distributed.ipynb) |
| 4 | Shipment events with a watermark | [`D4_3_streaming.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D4_3_streaming.ipynb) |
| 4 | Classification, masking and access tests | [`D4_4_governance.ipynb`](https://colab.research.google.com/github/SDAIAAcademy/data-engineering/blob/main/labs/D4_4_governance.ipynb) |

Exercises are marked **✏️ Exercise** and raise `NotImplementedError` until you fill them in. Complete reference
versions are in `solutions/`. Cells marked **✱ Stretch** are optional. Self-checks print ✅ or ❌.

Every lab works in its own folder under `artifacts/<lab>/`, so the shared data in `data/` never changes. Delete
`artifacts/` before running the course's `academy check`, which reports ignored files under `labs/`.

## The case study: Qafila Trading

Synthetic and deterministic (`qafila_data.py`, fixed seed), covering August to October 2026; no real personal data.
Qafila sells to 240 shops, restaurants and hotels and buys from 18 suppliers in five countries.

| Data | File | Contents |
|---|---|---|
| Order system extracts | `data/raw/extracts/` | customers, products, orders, order lines and prices as CSV; shipments as JSON lines |
| Order database | `data/raw/qafila_orders.sqlite` | the same orders as a transactional database (Lab 1.1) |
| Supplier price API | `data/raw/supplier_api/price_records.jsonl` | the records `qafila.SupplierAPI` serves, with pagination, a cursor and rate limits |
| November batch | `data/raw/supplier_api/batch_2026-11-01*.jsonl` | the batch that breaks the contract, and the fixed one (Labs 3.3, 3.4, capstone) |
| Supplier change feed | `data/raw/suppliers/` | the supplier table on 1 August and 31 October, and the change events between them |
| Shipment events | `data/raw/events/shipment_events.jsonl` | the event stream of Lab 4.3 |
| Reference states | `data/reference/` | finance's monthly margin and five answers, the old report, the reference supplier dimension, the keys of Labs 1.1 and 4.4 |
| Data contract | `contracts/supplier_prices.odcs.yaml` | the supplier feed's contract in the Open Data Contract Standard v3.1.0 |
| Models | `models/` | the staging and mart models as SQLMesh SQL files |

## Helpers

| File | What it is |
|---|---|
| `qafila.py` | paths, `check`, `reference`, `lab_dir`, `timed`, `warehouse` (a DuckDB file with the raw layer), `build_models`, `SupplierAPI` (a local paginated API with rate limits), `Log` (the file-backed event log) |
| `contract_gate.py` | compiles an ODCS contract's quality rules to SQL and runs them against a table |
| `qafila_data.py` | regenerates the data: `uv run python qafila_data.py --force` |

## The capstone

The brief, the rubric and the starter are in [`capstone/`](capstone/README.md).

**Windows and long folder paths.** If an import fails with "The filename or extension is too long", run
`git config core.longpaths true` and keep the virtual environment in a short folder: set `UV_PROJECT_ENVIRONMENT` to a
short path (for example a folder at the root of your drive) before `uv sync`.
