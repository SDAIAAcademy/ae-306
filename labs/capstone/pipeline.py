"""Qafila margin mart, end to end: your capstone pipeline.

    cd labs
    uv run python capstone/pipeline.py                  # the whole pipeline, November batch fixed
    uv run python capstone/pipeline.py --batch broken   # the contract must block: the mart is not refreshed

Each step below names the lab whose code it reuses. Replace each NotImplementedError with your own code; the
steps you have not built yet are reported, not fatal, so you can run the file at any point. The run writes
labs/artifacts/capstone/run_report.json (row counts, test results and run time per step): commit a copy of it as
evidence. The brief and the rubric are in capstone/README.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

LABS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LABS))

import qafila as Q  # noqa: E402
import contract_gate as G  # noqa: E402

OUT = Q.ARTIFACTS / "capstone"
DB = OUT / "qafila.duckdb"
REPORT: dict = {"steps": [], "row_counts": {}, "tests": {}}


def step(fn):
    """Run a step, time it, and record it in the report; a step not built yet is reported, not fatal."""
    def run(*args, **kwargs):
        t = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
            status = "done"
        except NotImplementedError as e:
            result, status = None, f"not built yet ({e})"
        REPORT["steps"].append({"step": fn.__name__, "status": status, "seconds": round(time.perf_counter() - t, 2)})
        print(f"{fn.__name__:22s} {status} in {REPORT['steps'][-1]['seconds']} s")
        return result
    return run


@step
def land_raw():
    """Raw layer: the nightly extracts as they arrived (supplied)."""
    OUT.mkdir(parents=True, exist_ok=True)
    con = Q.warehouse(DB, history=False)
    con.execute("CREATE OR REPLACE VIEW products AS SELECT * FROM raw.products")
    con.close()


@step
def ingest_supplier_api() -> int:
    """Incremental, idempotent load of the supplier price API: a key per version and a stored cursor (Lab 2.1)."""
    raise NotImplementedError("your code here")


@step
def ingest_supplier_changes() -> int:
    """Apply the change feed by log position and keep supplier history as a type 2 table (Lab 2.3)."""
    raise NotImplementedError("your code here")


@step
def contract_gate(batch_file: str) -> bool:
    """Land the November batch and run the ODCS contract; True when the refresh may go on (Lab 3.3)."""
    raise NotImplementedError("your code here")


@step
def build_models() -> dict:
    """Staging, dimensions, the fact at order-line grain and the monthly mart (Labs 3.1 and 3.2)."""
    raise NotImplementedError("your code here")


@step
def run_tests() -> dict:
    """Grain, keys, relationships and the reconciliation with finance's five answers (Lab 3.1)."""
    raise NotImplementedError("your code here")


@step
def write_iceberg() -> int:
    """The mart as an Iceberg table partitioned by month of the order date (Lab 4.1)."""
    raise NotImplementedError("your code here")


@step
def govern() -> dict:
    """Minimise, mask for the analyst role in its own database, and test access (Lab 4.4)."""
    raise NotImplementedError("your code here")


def report():
    with Q.connect(DB) as con:
        for (schema, table) in con.execute("SELECT table_schema, table_name FROM information_schema.tables "
                                            "WHERE table_schema IN ('raw', 'stg', 'mart') ORDER BY 1, 2").fetchall():
            REPORT["row_counts"][f"{schema}.{table}"] = con.execute(f"SELECT count(*) FROM {schema}.{table}").fetchall()[0][0]
    (OUT / "run_report.json").write_text(json.dumps(REPORT, indent=1, default=str), encoding="utf-8")
    passed = sum(1 for v in REPORT["tests"].values() if v)
    print(f"\n{passed} of {len(REPORT['tests'])} tests passed; report: {(OUT / 'run_report.json').relative_to(LABS).as_posix()}")
    for k, v in REPORT["tests"].items():
        print(("PASS " if v else "FAIL ") + k)
    return REPORT


def main(batch: str = "fixed") -> dict:
    t = time.perf_counter()
    land_raw()
    ingest_supplier_api()
    ingest_supplier_changes()
    ok = contract_gate("batch_2026-11-01.jsonl" if batch == "broken" else "batch_2026-11-01_fixed.jsonl")
    if ok is False:
        print("contract failed:", REPORT.get("contract_failed_checks"), "- the mart is not refreshed")
        REPORT["mart_refreshed"] = False
    else:
        build_models()
        run_tests()
        write_iceberg()
        govern()
        REPORT["mart_refreshed"] = True
    REPORT["total_seconds"] = round(time.perf_counter() - t, 2)
    return report()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--batch", choices=["fixed", "broken"], default="fixed")
    main(p.parse_args().batch)
