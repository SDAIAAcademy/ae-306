# <Project name>

> One sentence: which question the mart answers, for whom, and from which sources.

[Modern Data Engineering - SDAIA Academy](https://github.com/sdaiaacademy/data-engineering/)

**Author:** <name>
**Engine and tools:** <for example DuckDB, dlt, SQLMesh, Dagster, PyIceberg>, chosen because <your reason>

## How to run

```bash
uv sync
uv run python <your pipeline>.py                  # fixed batch: the mart is refreshed
uv run python <your pipeline>.py --batch broken   # broken batch: the refresh is blocked
```

It runs from a clean clone with no keys and no downloads beyond the packages.

## Results of the last run

| Table | Rows |
|---|---|
| fact (order line) | |
| dimensions | |
| monthly margin | |

| Test | Result |
|---|---|
| | |

| Step | Seconds |
|---|---|
| | |

**Finance's five questions:** your answer, the reference answer and the difference, for each.

## Model

- **Grain of the fact:** one row per <...>. Why this grain, and which question it could not answer at a coarser one.
- **Dimensions:** which are type 2, and why.
- **Freight:** how it is allocated, and the check that it is counted once.
- **Cost:** how each line finds the supplier price valid on its order date.

## Ingestion and history

The cursor, the keys, what a re-run does, and how deletes and late events in the change feed are handled.

## Contract and tests

The contract's rules, who owns it, and what happens to a batch that fails it. The tests on the mart and why each exists.

## Orchestration and recovery

The run log of the broken batch: what was caught, what was not refreshed, and the backfill after the fix.

## Table format

The partitioning, the schema change you made, the second engine, and a query against an earlier snapshot.

## Governance

| Field | Level | Personal? | Why | Analyst sees |
|---|---|---|---|---|
| | | | | |

The minimisation rule, the masking and the access tests.

## Evidence

Link the files that back every number above: the run reports, the run logs and the transcripts of any coding agent.

## AI assistance

Which coding agents or assistants you used, and for what. You are answerable for every decision and number here.

## Limitations

What does not work yet, and what production would need.
