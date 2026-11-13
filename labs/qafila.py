"""Helpers shared by the labs of AE-306 Modern Data Engineering (Qafila Trading).

    import qafila as Q

Data: Q.ensure_data() writes data/raw/ and data/reference/ with qafila_data.py (seed 306) when they are missing.
Reference states: Q.warehouse(), Q.build_models(), Q.mart_table() build what a lab starts from, so no lab needs another.
Services: Q.SupplierAPI (the paginated supplier price API, in process) and Q.Log (a single-broker event log on disk).
Checks: Q.check(condition, message) prints a tick or a cross; with DE_STRICT=1 a cross stops the run.
Quick mode: DE_QUICK=1 makes the heavy steps smaller (Q.pick(full, quick)).
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LABS = Path(__file__).resolve().parent
DATA = LABS / "data"
RAW = DATA / "raw"
EXTRACTS = RAW / "extracts"
REF = DATA / "reference"
MODELS = LABS / "models"
ARTIFACTS = LABS / "artifacts"
QUICK = os.environ.get("DE_QUICK", "0") == "1"
STRICT = os.environ.get("DE_STRICT", "0") == "1"
RATES = {"SAR": 1.0, "USD": 3.75, "AED": 1.0211}

# The order in which the reference models build (each reads only the ones before it).
MODEL_ORDER = ["stg_orders", "stg_order_lines", "stg_products", "stg_customers", "stg_prices", "stg_shipments",
               "dim_customer", "dim_product", "dim_supplier", "fct_order_line", "margin_monthly"]


def pick(full, quick):
    """The full value, or the small one in quick mode."""
    return quick if QUICK else full


def check(ok: bool, message: str) -> bool:
    print(("✅ " if ok else "❌ ") + message)
    if not ok and STRICT:
        raise AssertionError(message)
    return bool(ok)


def ensure_data(force: bool = False) -> Path:
    import qafila_data
    return qafila_data.main(force=force)


def reference(name: str):
    """A reference result written by the data generator (data/reference/<name>.json)."""
    ensure_data()
    return json.loads((REF / f"{name}.json").read_text(encoding="utf-8"))


def lab_dir(name: str, reset: bool = True) -> Path:
    """A fresh working folder for one lab, under labs/artifacts/ (git ignores it)."""
    d = ARTIFACTS / name
    if reset and d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    return d


def timed(fn, repeat: int = 3) -> tuple[float, object]:
    """Best wall time of `repeat` runs, in seconds, and the last result."""
    best, out = float("inf"), None
    for _ in range(repeat):
        t = time.perf_counter()
        out = fn()
        best = min(best, time.perf_counter() - t)
    return best, out


def mb(n_bytes: int) -> str:
    return f"{n_bytes / 1e6:,.2f} MB"


def folder_bytes(path: Path) -> int:
    path = Path(path)
    return path.stat().st_size if path.is_file() else sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def posix(path: Path) -> str:
    """A path as DuckDB and Iceberg like it on every system: forward slashes."""
    return Path(path).resolve().as_posix()


# ------------------------------------------------------------------------------------------- warehouse states
def connect(path: Path | str | None = None):
    import duckdb
    con = duckdb.connect(str(path) if path else ":memory:")
    con.execute("SET TimeZone = 'Asia/Riyadh'")
    return con


def warehouse(path: Path | str | None = None, history: bool = True):
    """Reference state: the raw extracts loaded as tables in schema raw, as the nightly load leaves them."""
    ensure_data()
    con = connect(path)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    e = posix(EXTRACTS)
    for t in ("orders", "order_lines", "customers", "products", "prices"):
        con.execute(f"CREATE OR REPLACE TABLE raw.{t} AS SELECT * FROM read_csv('{e}/{t}.csv', all_varchar = true)")
    con.execute(f"CREATE OR REPLACE TABLE raw.shipments AS SELECT * FROM read_json('{e}/shipments.jsonl', format = 'newline_delimited')")
    if history:
        con.execute(f"CREATE OR REPLACE TABLE raw.supplier_history AS SELECT * FROM read_csv('{posix(REF)}/dim_supplier.csv', all_varchar = true)")
    return con


LINES_WIDE = """
    SELECT CAST(l.order_id AS BIGINT) AS order_id, CAST(l.line_no AS INTEGER) AS line_no,
           CAST(o.order_date AS DATE) AS order_date, o.status, o.customer_id, l.product_id, p.category, p.supplier_id,
           l.unit, CAST(l.qty AS INTEGER) AS qty,
           CAST(l.qty AS INTEGER) * CASE WHEN l.unit = 'carton' THEN CAST(p.units_per_carton AS INTEGER) ELSE 1 END AS qty_pieces,
           CAST(l.qty AS INTEGER) * CAST(l.unit_price_sar AS DOUBLE) * (1 - CAST(l.discount_pct AS DOUBLE) / 100) AS revenue
    FROM raw.order_lines l JOIN raw.orders o USING (order_id) JOIN raw.products p USING (product_id)"""


def lines_wide(con, name: str = "lines"):
    """Reference state: one row per extract line with its order date, status and revenue (duplicates kept)."""
    con.execute(f"CREATE OR REPLACE TABLE {name} AS {LINES_WIDE}")
    return con.table(name)


def model_sql(name: str, folder: Path = MODELS) -> tuple[str, str]:
    """(table name, SELECT statement) of one model file: the MODEL header is SQLMesh's, the body plain SQL."""
    text = (Path(folder) / f"{name}.sql").read_text(encoding="utf-8")
    m = re.match(r"\s*MODEL\s*\((.*?)\);\s*", text, re.S)
    table = re.search(r"name\s+([\w.]+)", m.group(1)).group(1)
    return table, text[m.end():].strip().rstrip(";")


def build_models(con, folder: Path = MODELS, names: list[str] | None = None) -> list[str]:
    """Reference state: run the models in order with plain DuckDB (no framework)."""
    built = []
    for name in names or MODEL_ORDER:
        table, body = model_sql(name, folder)
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {table.split('.')[0]}")
        con.execute(f"CREATE OR REPLACE TABLE {table} AS {body}")
        built.append(table)
    return built


def mart_table(con=None):
    """Reference state for Day 4: the margin mart at order-line grain, with its dimensions, as an Arrow table."""
    con = con or warehouse()
    if not con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'fct_order_line'").fetchall()[0][0]:
        build_models(con)
    return con.sql("""
        SELECT f.order_id, f.line_no, f.order_date, strftime(f.order_date, '%Y-%m') AS month,
               c.city, c.customer_type, p.category, f.product_id, coalesce(s.country, 'Unknown') AS supplier_country,
               f.qty_pieces, f.revenue, f.cost, f.revenue - f.cost AS margin, f.freight
        FROM mart.fct_order_line f
        JOIN mart.dim_customer c USING (customer_id)
        JOIN mart.dim_product p USING (product_id)
        LEFT JOIN mart.dim_supplier s USING (supplier_key)
        ORDER BY f.order_id, f.line_no""").to_arrow_table()


# ------------------------------------------------------------------------------------------- the supplier API
class SupplierAPI:
    """The supplier price API, served in process on 127.0.0.1.

    GET /prices?updated_since=<iso>&cursor=<opaque>  -> {"data": [...], "next_cursor": "..." | null}
    Pages of `page_size` records ordered by (updated_at, price_id). Every `throttle_every`-th request answers 429
    with a Retry-After header. `release` 1 serves what existed on 15 October, release 2 everything to 31 October; `until` (an ISO date) overrides it.
    `fail_first` makes the first n requests answer 503 (a flaky source, for the retry lab).
    """

    def __init__(self, release: int = 1, page_size: int = 20, throttle_every: int = 4, fail_first: int = 0,
                 until: str | None = None):
        ensure_data()
        lines = (RAW / "supplier_api" / "price_records.jsonl").read_text(encoding="utf-8").splitlines()
        self.records = [json.loads(x) for x in lines if x.strip()]
        self.release, self.page_size, self.throttle_every, self.fail_first = release, page_size, throttle_every, fail_first
        self.until = until
        self.requests = 0
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                api.requests += 1
                if api.requests <= api.fail_first:
                    return self._send(503, {"error": "service unavailable"})
                if api.throttle_every and api.requests % api.throttle_every == 0:
                    return self._send(429, {"error": "too many requests"}, {"Retry-After": "0.2"})
                from urllib.parse import parse_qs, urlparse
                url = urlparse(self.path)
                if url.path != "/prices":
                    return self._send(404, {"error": "not found"})
                q = {k: v[0] for k, v in parse_qs(url.query).items()}
                since = q.get("updated_since", "")
                start = 0
                if q.get("cursor"):
                    since, start = json.loads(base64.urlsafe_b64decode(q["cursor"]).decode())
                rows = [r for r in api.visible() if r["updated_at"] > since]
                page = rows[start:start + api.page_size]
                more = start + api.page_size < len(rows)
                cursor = base64.urlsafe_b64encode(json.dumps([since, start + api.page_size]).encode()).decode() if more else None
                self._send(200, {"data": page, "next_cursor": cursor})

            def _send(self, code, body, headers=None):
                data = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def visible(self):
        cut = self.until or ("2026-10-16" if self.release == 1 else "9999")
        return [r for r in self.records if r["updated_at"] < cut]

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


# ------------------------------------------------------------------------------------------- a single-broker log
class Log:
    """An append-only log on disk with offsets and committed consumer positions, like one partition of a broker.

    produce(record) -> offset; read(offset, max_records) -> [(offset, record)]; commit(group, offset); committed(group)
    """

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / "partition-0.log"
        self.offsets_path = self.folder / "consumer_offsets.json"
        self.path.touch()
        self._index = [0]
        with self.path.open("rb") as f:
            for line in f:
                self._index.append(self._index[-1] + len(line))
        self._index.pop()

    def produce(self, record: dict) -> int:
        line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
        with self.path.open("ab") as f:
            pos = f.tell()
            f.write(line)
        self._index.append(pos)
        return len(self._index) - 1

    @property
    def end_offset(self) -> int:
        return len(self._index)

    def read(self, offset: int, max_records: int = 100) -> list[tuple[int, dict]]:
        out = []
        if offset >= len(self._index):
            return out
        with self.path.open("rb") as f:
            f.seek(self._index[offset])
            for i in range(offset, min(offset + max_records, len(self._index))):
                out.append((i, json.loads(f.readline())))
        return out

    def committed(self, group: str) -> int:
        if not self.offsets_path.exists():
            return 0
        return json.loads(self.offsets_path.read_text(encoding="utf-8")).get(group, 0)

    def commit(self, group: str, next_offset: int) -> None:
        state = json.loads(self.offsets_path.read_text(encoding="utf-8")) if self.offsets_path.exists() else {}
        state[group] = next_offset
        self.offsets_path.write_text(json.dumps(state), encoding="utf-8")


def show(rel_or_df, n: int = 10):
    """Print the first rows of a DuckDB relation, a Polars or pandas frame, or an Arrow table."""
    try:
        import duckdb
        if isinstance(rel_or_df, duckdb.DuckDBPyRelation):
            rel_or_df.show(max_rows=n)
            return
    except ImportError:
        pass
    if hasattr(rel_or_df, "head"):
        print(rel_or_df.head(n))
    elif hasattr(rel_or_df, "slice"):
        print(rel_or_df.slice(0, n).to_pandas())
    else:
        print(rel_or_df)
