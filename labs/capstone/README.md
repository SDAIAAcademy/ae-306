# Capstone · The Qafila margin mart

The capstone is individual. You build **Qafila Trading's margin mart, from the raw extracts to an Apache Iceberg
table**, either on the starter in this folder or on your own code. You publish it in a **public repository**. The
assessor re-runs it from a clean checkout. Then you defend it in an **eight-minute defence**: one modelling decision
of your choice, and one transformation the assessor selects.

## The brief

Finance cannot agree with sales on the gross margin. The old report counts cancelled orders and re-sent lines, joins
freight at the wrong grain and prices every line at today's supplier cost. Qafila wants one mart that answers the
finance team's five questions (`data/reference/finance_answers.json`) and that a broken supplier feed cannot corrupt.

Your mart must:

1. **Ingest** the supplier price API incrementally (a key per version and a stored cursor: a re-run adds nothing) and
   apply the supplier change feed in log order, keeping supplier history as a type 2 table with no overlapping ranges.
2. **Model** a star schema at order-line grain: the fact, the customer, product and supplier dimensions, and a monthly
   margin table. Each line is costed at the supplier price valid on its order date, and freight is allocated once.
3. **Test** the grain, the keys, the relationships and the reconciliation with finance's answers, and gate every
   supplier batch with the data contract (`contracts/supplier_prices.odcs.yaml`, or your own version of it).
4. **Orchestrate** the steps so that a batch that breaks the contract blocks the refresh and leaves yesterday's mart
   in place, with retries on the API and a backfill of the affected month after the fix.
5. **Store** the mart as an Iceberg table partitioned by month, read it from a second engine, and query an earlier
   snapshot.
6. **Govern** the customer and supplier fields: a classification register under the national levels, minimisation,
   masking for the analyst role and access tests.

Use the course's synthetic data, or data you generate yourself. No personal data and no internal data from your entity.

## Rubric

| Criterion | Points |
|---|---|
| Correctness of the mart | 25 |
| Ingestion and history | 20 |
| Tests and contract | 20 |
| Orchestration and recovery | 15 |
| Table format and governance | 10 |
| Reproducibility | 10 |

The repository is assessed on this rubric. The defence then confirms that the work is yours.

**AI policy.** AI-full: coding agents are allowed. Keep their transcripts and your run logs with timestamps. They are
part of the evidence of authorship, together with the commit history and the defence.

## Getting started

```bash
cd labs
uv run python capstone/pipeline.py                  # runs the steps you have built; the others are reported
uv run python capstone/pipeline.py --batch broken   # the November batch that breaks the contract
```

`pipeline.py` has the eight steps of the mart, each with a docstring and a `NotImplementedError` to replace. The first
step, landing the raw extracts, is done for you. Each run writes `artifacts/capstone/run_report.json` with row counts,
test results and the run time of each step. Commit a copy of the last report of each kind (fixed and broken batch) as
evidence.

The labs closest to each step:

| Step | Start from |
|---|---|
| `ingest_supplier_api` | Lab 2.1 (cursor and keys), Lab 2.2 (the same with dlt) |
| `ingest_supplier_changes` | Lab 2.3 |
| cleaning costs and supplier names | Lab 2.4 |
| `contract_gate` | Lab 3.3, `contract_gate.py` |
| `build_models` | Lab 3.1 (grain, freight, cost as of the order date), Lab 3.2 (`models/`, SQLMesh) |
| `run_tests` | Lab 1.2 and Lab 3.1 (reconciliation) |
| orchestration, retries and backfill | Lab 3.4 (Dagster) |
| `write_iceberg` | Lab 4.1 |
| `govern` | Lab 4.4, `data/reference/classification.json` is **not** yours to copy: write your own register |

You may replace the plain functions with Dagster assets, SQLMesh models or dlt resources. The starter's shape is a
suggestion; the requirements above are not.

## Timeline

| When | What |
|---|---|
| Day 4, after Session 4 | Run the starter. Build ingestion and the contract gate. Copy `TEMPLATE_README.md` as your README. |
| Day 4, evening | Build the models and the tests until finance's five answers reconcile. |
| Day 5, morning | Orchestration and the broken batch, Iceberg, governance. Test a clean clone. Publish. |
| Day 5, afternoon | The eight-minute defence. |

## The defence (eight minutes)

1. **Three minutes.** One modelling decision: what you chose, the alternative, and the number that shows it was right.
2. **Three minutes.** A transformation the assessor selects from your repository: what it reads, what it writes and
   what would break it.
3. **Two minutes.** The run log of the broken batch: what was caught and what stayed in place.

The assessor may ask about any decision in the README.
