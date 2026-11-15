"""Qafila margin mart, end to end: the trainer's reference solution of the capstone.

    cd labs
    uv run python solutions/capstone_pipeline.py                  # the whole pipeline, November batch fixed
    uv run python solutions/capstone_pipeline.py --batch broken   # the contract blocks: the mart is not refreshed
    uv run python solutions/capstone_pipeline.py --backfill 2026-10   # after the fix: rebuild October only

Writes into labs/artifacts/capstone/ (git ignores it): qafila.duckdb, the Iceberg warehouse, analyst.duckdb and
run_report.json (row counts, test results and run time per step). labs/capstone/pipeline.py is the participants'
starter: the same steps, with the bodies marked BEGIN/END SOLUTION here replaced by NotImplementedError
(written by _tools/make_capstone_starter.py).
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
    # BEGIN SOLUTION
    import requests
    api = Q.SupplierAPI(release=2)
    cols = ["price_id", "product_id", "supplier_name", "cost", "currency", "unit", "valid_from", "updated_at", "incoterm"]
    with Q.connect(DB) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS raw.supplier_prices (price_id VARCHAR, product_id VARCHAR, supplier_name VARCHAR,
            cost VARCHAR, currency VARCHAR, unit VARCHAR, valid_from DATE, updated_at TIMESTAMPTZ, incoterm VARCHAR,
            PRIMARY KEY (price_id, updated_at))""")
        con.execute("CREATE TABLE IF NOT EXISTS raw._load_state (source VARCHAR PRIMARY KEY, cursor VARCHAR)")
        inserted = []
        for _ in range(2):                                         # run twice: the second must add nothing
            row = con.execute("SELECT cursor FROM raw._load_state WHERE source = 'supplier_prices'").fetchall()
            params, new = {"updated_since": row[0][0] if row else ""}, []
            while True:
                r = requests.get(f"{api.url}/prices", params=params, timeout=10)
                if r.status_code == 429:
                    time.sleep(float(r.headers.get("Retry-After", "1")))
                    continue
                r.raise_for_status()
                page = r.json()
                new += page["data"]
                if not page["next_cursor"]:
                    break
                params = {"cursor": page["next_cursor"]}
            before = con.execute("SELECT count(*) FROM raw.supplier_prices").fetchall()[0][0]
            con.execute("BEGIN TRANSACTION")
            if new:
                con.executemany(f"INSERT OR IGNORE INTO raw.supplier_prices VALUES ({', '.join('?' * len(cols))})",
                                [[x.get(c) for c in cols] for x in new])
                con.execute("INSERT OR REPLACE INTO raw._load_state VALUES ('supplier_prices', ?)", [max(x["updated_at"] for x in new)])
            con.execute("COMMIT")
            inserted.append(con.execute("SELECT count(*) FROM raw.supplier_prices").fetchall()[0][0] - before)
    api.stop()
    REPORT["tests"]["api_rerun_adds_nothing"] = inserted[1] == 0
    return inserted[0]
    # END SOLUTION


@step
def ingest_supplier_changes() -> int:
    """Apply the change feed by log position and keep supplier history as a type 2 table (Lab 2.3)."""
    # BEGIN SOLUTION
    s = Q.posix(Q.RAW / "suppliers")
    cols = ["supplier_id", "name_en", "name_ar", "country", "currency", "payment_terms_days", "contact_name",
            "contact_email", "iban", "contract_ref"]
    with Q.connect(DB) as con:
        con.execute(f"""CREATE OR REPLACE TABLE raw.supplier_feed AS
            SELECT op, before, after, source.lsn AS lsn, make_timestamptz(source.ts_ms * 1000) AS changed_at
            FROM read_json('{s}/supplier_changes.jsonl', format = 'newline_delimited')""")
        con.execute(f"""CREATE OR REPLACE TABLE raw.supplier_history AS
            WITH versions AS (
              SELECT {', '.join(cols)}, TIMESTAMPTZ '2026-08-01 00:00:00+03' AS valid_from, 0 AS lsn, false AS is_delete
              FROM read_csv('{s}/suppliers_2026-08-01.csv')
              UNION ALL
              SELECT DISTINCT ON (lsn) {', '.join('after.' + c for c in cols)}, changed_at, lsn, false
              FROM raw.supplier_feed WHERE op IN ('c', 'u')
              UNION ALL
              SELECT DISTINCT ON (lsn) before.supplier_id, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, changed_at, lsn, true
              FROM raw.supplier_feed WHERE op = 'd'),
            ranged AS (SELECT *, lead(valid_from) OVER (PARTITION BY supplier_id ORDER BY lsn) AS valid_to FROM versions)
            SELECT {', '.join(cols)}, valid_from, valid_to FROM ranged WHERE NOT is_delete""")
        overlaps = con.execute("""SELECT count(*) FROM raw.supplier_history a JOIN raw.supplier_history b USING (supplier_id)
            WHERE a.valid_from < b.valid_from AND coalesce(a.valid_to, TIMESTAMPTZ '9999-12-31 00:00:00+00') > b.valid_from""").fetchall()[0][0]
        n = con.execute("SELECT count(*) FROM raw.supplier_history").fetchall()[0][0]
    REPORT["tests"]["supplier_history_no_overlap"] = overlaps == 0
    return n
    # END SOLUTION


@step
def contract_gate(batch_file: str) -> bool:
    """Land the November batch and run the ODCS contract; True when the refresh may go on (Lab 3.3)."""
    # BEGIN SOLUTION
    contract = G.load(LABS / "contracts" / "supplier_prices.odcs.yaml")
    with Q.connect(DB) as con:
        con.execute(f"CREATE OR REPLACE TABLE raw.november_batch AS SELECT * FROM read_json('{Q.posix(Q.RAW / 'supplier_api' / batch_file)}')")
        results = G.run(con, contract, "raw.november_batch")
    failed = [r["id"] for r in results if not r["passed"]]
    REPORT["tests"]["contract_" + batch_file] = not failed
    REPORT["contract_failed_checks"] = failed
    return not failed
    # END SOLUTION


@step
def build_models() -> dict:
    """Staging, dimensions, the fact at order-line grain and the monthly mart (Labs 3.1 and 3.2)."""
    # BEGIN SOLUTION
    with Q.connect(DB) as con:
        con.execute("CREATE OR REPLACE TABLE raw.supplier_history AS SELECT * REPLACE (CAST(valid_from AS VARCHAR) AS valid_from, "
                    "CAST(valid_to AS VARCHAR) AS valid_to) FROM raw.supplier_history")
        Q.build_models(con)
        return {t: con.execute(f"SELECT count(*) FROM {t}").fetchall()[0][0]
                for t in ("mart.dim_customer", "mart.dim_product", "mart.dim_supplier", "mart.fct_order_line", "mart.margin_monthly")}
    # END SOLUTION


@step
def backfill(month: str) -> int:
    """After a fix, rebuild one month of the monthly mart and leave the other months as they were (Lab 3.4)."""
    # BEGIN SOLUTION
    with Q.connect(DB) as con:
        before = dict(con.execute("SELECT month, margin FROM mart.margin_monthly").fetchall())
        con.execute("BEGIN")                      # delete and insert together: a backfill can run twice
        con.execute("DELETE FROM mart.margin_monthly WHERE month = ?", [month])
        con.execute("""INSERT INTO mart.margin_monthly
            SELECT strftime(order_date, '%Y-%m') AS month, round(sum(revenue), 2), round(sum(cost), 2),
                   round(sum(revenue) - sum(cost), 2), round(100 * (sum(revenue) - sum(cost)) / sum(revenue), 2)
            FROM mart.fct_order_line WHERE strftime(order_date, '%Y-%m') = ? GROUP BY 1""", [month])
        con.execute("COMMIT")
        after = dict(con.execute("SELECT month, margin FROM mart.margin_monthly").fetchall())
    REPORT["backfill"] = {"month": month, "months_rebuilt": 1, "months_left_alone": len(after) - 1}
    REPORT["tests"]["backfill_rebuilds_one_month"] = month in after and all(after.get(m) == v for m, v in before.items() if m != month)
    return 1
    # END SOLUTION


@step
def run_tests() -> dict:
    """Grain, keys, relationships and the reconciliation with finance's five answers (Lab 3.1)."""
    # BEGIN SOLUTION
    fa = Q.reference("finance_answers")
    with Q.connect(DB) as con:
        q = lambda sql: con.execute(sql).fetchall()[0][0]  # noqa: E731
        t = {
            "fact_grain_unique": q("SELECT count(*) - count(DISTINCT (order_id, line_no)) FROM mart.fct_order_line") == 0,
            "fact_customer_known": q("SELECT count(*) FROM mart.fct_order_line WHERE customer_id NOT IN (SELECT customer_id FROM mart.dim_customer)") == 0,
            "fact_supplier_version_found": q("SELECT count(*) FROM mart.fct_order_line WHERE supplier_key IS NULL") == 0,
            "cost_not_null": q("SELECT count(*) FROM mart.fct_order_line WHERE cost IS NULL") == 0,
            "freight_counted_once": abs(q("SELECT sum(freight) FROM mart.fct_order_line") - q("SELECT sum(freight_sar) FROM stg.shipments")) < 1,
            "monthly_margin_matches_finance": all(
                abs(float(m) - r["margin"]) < 1 for (m,), r in zip(con.execute("SELECT margin FROM mart.margin_monthly ORDER BY month").fetchall(), fa["q1_monthly"])),
        }
    REPORT["tests"].update(t)
    return t
    # END SOLUTION


@step
def write_iceberg() -> int:
    """The mart as an Iceberg table partitioned by month of the order date (Lab 4.1)."""
    # BEGIN SOLUTION
    import pyarrow as pa
    from pyiceberg.catalog.sql import SqlCatalog
    from pyiceberg.transforms import MonthTransform
    with Q.connect(DB) as con:
        mart = Q.mart_table(con)
    mart = mart.cast(pa.schema([pa.field(f.name, pa.float64() if pa.types.is_decimal(f.type) else f.type) for f in mart.schema]))
    wh = OUT / "iceberg"
    wh.mkdir(parents=True, exist_ok=True)
    catalog = SqlCatalog("qafila", uri=f"sqlite:///{Q.posix(wh)}/catalog.db", warehouse=Q.posix(wh))
    catalog.create_namespace_if_not_exists("mart")
    if catalog.table_exists("mart.margin_lines"):
        catalog.drop_table("mart.margin_lines")
    table = catalog.create_table("mart.margin_lines", schema=mart.schema)
    with table.update_spec() as spec:
        spec.add_field("order_date", MonthTransform(), "order_month")
    table.append(mart)
    n = table.scan().to_arrow().num_rows
    REPORT["tests"]["iceberg_rows_equal_mart"] = n == mart.num_rows
    return n
    # END SOLUTION


@step
def govern() -> dict:
    """Minimise, mask for the analyst role in its own database, and test access (Lab 4.4)."""
    # BEGIN SOLUTION
    import duckdb
    analyst = OUT / "analyst.duckdb"
    analyst.unlink(missing_ok=True)
    with Q.connect(DB) as con:
        con.execute(f"ATTACH '{Q.posix(analyst)}' AS analyst")
        con.execute(r"""CREATE TABLE analyst.customers AS SELECT customer_id, name, customer_type, city,
            regexp_replace(contact_name, '(\w)\w*', '\1.', 'g') AS contact_name,
            left(mobile, 4) || repeat('*', length(mobile) - 6) || right(mobile, 2) AS mobile,
            regexp_replace(email, '^[^@]+', '***') AS email FROM raw.customers""")
        con.execute("""CREATE TABLE analyst.margin_lines AS SELECT f.order_id, f.line_no, f.order_date, c.customer_type, c.city,
            p.category, f.revenue, f.cost, f.freight FROM mart.fct_order_line f JOIN mart.dim_customer c USING (customer_id)
            JOIN mart.dim_product p USING (product_id)""")
        con.execute("DETACH analyst")
    with duckdb.connect(str(analyst), read_only=True) as a:
        values = [str(v) for t in ("customers", "margin_lines") for row in a.execute(f"SELECT * FROM {t}").fetchall() for v in row]
        try:
            a.execute("SELECT * FROM raw.customers").fetchall()
            raw_hidden = False
        except duckdb.Error:
            raw_hidden = True
    t = {"analyst_cannot_read_raw": raw_hidden,
         "analyst_sees_no_mobile": not any(re.search(r"\+9665\d{8}", v) for v in values),
         "analyst_sees_no_email": not any(re.search(r"^[^*\s][^@\s]*@", v) for v in values)}
    REPORT["tests"].update(t)
    return t
    # END SOLUTION


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


def main(batch: str = "fixed", backfill_month: str | None = None) -> dict:
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
        if backfill_month:
            backfill(backfill_month)
        run_tests()
        write_iceberg()
        govern()
        REPORT["mart_refreshed"] = True
    REPORT["total_seconds"] = round(time.perf_counter() - t, 2)
    return report()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--batch", choices=["fixed", "broken"], default="fixed")
    p.add_argument("--backfill", metavar="YYYY-MM", help="after a fix: rebuild this month of the monthly mart only")
    args = p.parse_args()
    main(args.batch, args.backfill)
