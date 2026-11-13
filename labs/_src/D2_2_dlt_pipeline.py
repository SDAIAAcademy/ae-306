# %% [markdown]
# # Lab 2.2 · The supplier load with dlt
#
# Day 2 · Session 2 (Declarative ingestion pipelines) · 25 min. In Lab 2.1 you wrote paging, back-off, a key and a
# stored cursor by hand. Here you declare the same load with dlt, an open-source Python ingestion library: a
# resource with an incremental cursor and a primary key, merged into DuckDB. Then the supplier adds a column
# (`incoterm`) and you watch the pipeline absorb it and record it.
#
# **Reference state.** `Q.SupplierAPI(until="2026-10-01")` serves the API as it stood at the end of September
# (before `incoterm` existed); `release=2` everything to 31 October. Nothing from another lab is needed.
#
# **Tasks**
# - [ ] 1 · Declare the resource and run the pipeline (7')
# - [ ] 2 · Read what was created: tables, columns, state (5')
# - [ ] 3 · New data with a new column: run again (7')
# - [ ] 4 · Prove the merge: no duplicates, corrections applied (6')
# - [ ] ✱ Stretch · Freeze the schema and watch the next new column fail

# %%
import os, sys, subprocess
from pathlib import Path

IN_COLAB = "google.colab" in sys.modules
if IN_COLAB:
    REPO_URL = "https://github.com/SDAIAAcademy/data-engineering.git"
    if not Path("/content/data-engineering").exists():
        subprocess.run(["git", "clone", "-q", REPO_URL, "/content/data-engineering"], check=True)
    os.chdir("/content/data-engineering/labs")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements-colab.txt"], check=True)
else:
    while not Path("qafila.py").exists() and Path.cwd() != Path.cwd().parent:
        os.chdir("..")  # solutions/ notebooks run from labs/
sys.path.insert(0, os.getcwd())

import qafila as Q

WORK = Q.lab_dir("D2_2")
os.environ["DLT_DATA_DIR"] = str(WORK / "dlt_home")          # keep dlt's working state inside the lab folder
os.environ["RUNTIME__LOG_LEVEL"] = "WARNING"

import time

import dlt
import duckdb
import requests

print("dlt", dlt.__version__)

# %% [markdown]
# ## 1 · Declare the resource and run the pipeline (7')
#
# A dlt **resource** is a generator that yields records. Three declarations replace most of Lab 2.1's code:
# - `primary_key="price_id"` and `write_disposition="merge"`: a record with a known key replaces the stored one;
# - `dlt.sources.incremental("updated_at")`: dlt keeps the highest `updated_at` seen in its **state**, stored in
#   the destination, and passes it to the next run.
#
# ✏️ **Exercise** · Complete `supplier_prices(base_url, updated_at=...)`: request `/prices` with
# `updated_since=updated_at.last_value` (an empty string on the first run), follow `next_cursor`, wait on a `429`,
# and `yield` each page's `data`.

# %%
@dlt.resource(name="supplier_prices", primary_key="price_id", write_disposition="merge")
def supplier_prices(base_url: str, updated_at=dlt.sources.incremental("updated_at", initial_value="")):
    # BEGIN SOLUTION
    params = {"updated_since": updated_at.last_value or ""}
    while True:
        resp = requests.get(f"{base_url}/prices", params=params, timeout=10)
        if resp.status_code == 429:
            time.sleep(float(resp.headers.get("Retry-After", "1")))
            continue
        resp.raise_for_status()
        page = resp.json()
        yield page["data"]
        if not page["next_cursor"]:
            break
        params = {"cursor": page["next_cursor"]}
    # END SOLUTION


DB = WORK / "qafila_dlt.duckdb"


def new_pipeline():
    return dlt.pipeline(pipeline_name="qafila_supplier_prices", destination=dlt.destinations.duckdb(str(DB)),
                        dataset_name="raw_suppliers", pipelines_dir=str(WORK / "pipelines"))


def count(sql: str) -> int:
    with duckdb.connect(str(DB), read_only=True) as c:
        return c.execute(sql).fetchall()[0][0]


# %%
api = Q.SupplierAPI(until="2026-10-01")
pipeline = new_pipeline()
try:
    info = pipeline.run(supplier_prices(api.url))
except Exception as e:  # noqa: BLE001 - safety net for a skipped exercise
    if "NotImplementedError" not in repr(e):
        raise
    import json as _json
    rows = [_json.loads(x) for x in (Q.RAW / "supplier_api" / "price_records.jsonl").read_text(encoding="utf-8").splitlines()]
    info = pipeline.run(dlt.resource([r for r in rows if r["updated_at"] < "2026-10-01"], name="supplier_prices",
                                     primary_key="price_id", write_disposition="merge"))
print(info)
api.stop()
n1 = count("SELECT count(*) FROM raw_suppliers.supplier_prices")
Q.check(n1 == 93, f"{n1} prices loaded from the September state of the API")

# %% [markdown]
# ## 2 · Read what was created: tables, columns, state (5')

# %%
with duckdb.connect(str(DB), read_only=True) as c:
    print(c.sql("SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw_suppliers' ORDER BY 1"))
    print(c.sql("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'raw_suppliers' "
                "AND table_name = 'supplier_prices' ORDER BY ordinal_position"))
    print(c.sql("SELECT load_id, status, inserted_at FROM raw_suppliers._dlt_loads"))
state = pipeline.state["sources"]
print("stored cursor:", state)

# %% [markdown]
# 🔍 Three things you wrote by hand in Lab 2.1 are now tables: the data, the **load history** (`_dlt_loads`, one row
# per load package) and the **state** with the cursor (`_dlt_pipeline_state`), all in the destination. dlt also
# added `_dlt_load_id` and `_dlt_id` to every row: which load brought it.

# %% [markdown]
# ## 3 · New data with a new column: run again (7')
#
# From October, the API sends `incoterm` (the delivery terms: DAP, CIF, FOB). Run the same pipeline against
# the 31 October state.
#
# ✏️ **Exercise** · Run the pipeline again with a **new** `Q.SupplierAPI(release=2)` and store the load info in
# `info2`. Then find the new column in the destination.

# %%
api = Q.SupplierAPI(release=2)
pipeline = new_pipeline()  # the same name: dlt restores the state from the destination
# BEGIN SOLUTION
info2 = pipeline.run(supplier_prices(api.url))
# END SOLUTION
api.stop()

# %%
try:
    info2
except NameError:  # safety net
    api = Q.SupplierAPI(release=2)
    info2 = pipeline.run(supplier_prices(api.url))
    api.stop()
with duckdb.connect(str(DB), read_only=True) as c:
    cols = [r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'raw_suppliers' "
                                     "AND table_name = 'supplier_prices'").fetchall()]
    print(c.sql("SELECT incoterm, count(*) AS prices FROM raw_suppliers.supplier_prices GROUP BY 1 ORDER BY 1"))
    loads = c.execute("SELECT count(*) FROM raw_suppliers._dlt_loads").fetchall()[0][0]
Q.check("incoterm" in cols, "the new column was added to the table, not dropped")
Q.check(loads == 2, "two loads recorded")
print("schema version:", pipeline.default_schema.version, "| tables:", list(pipeline.default_schema.data_table_names()))

# %% [markdown]
# ## 4 · Prove the merge: no duplicates, corrections applied (6')
#
# The reference is computed from the source file: the latest version of every `price_id`.
#
# ✏️ **Exercise** · Write the two checks: no `price_id` appears twice in the table, and every stored `cost` equals
# the cost of the latest version in `latest` (a dict `price_id -> cost`).

# %%
import json

src = [json.loads(x) for x in (Q.RAW / "supplier_api" / "price_records.jsonl").read_text(encoding="utf-8").splitlines()]
latest = {}
for r in sorted(src, key=lambda r: r["updated_at"]):
    latest[r["price_id"]] = r["cost"]
with duckdb.connect(str(DB), read_only=True) as c:
    stored = dict(c.execute("SELECT price_id, cost FROM raw_suppliers.supplier_prices").fetchall())
    # BEGIN SOLUTION
    dupes = c.execute("SELECT count(*) - count(DISTINCT price_id) FROM raw_suppliers.supplier_prices").fetchall()[0][0]
    wrong = [p for p, cost in latest.items() if stored.get(p) != cost]
    # END SOLUTION

# %%
try:
    dupes, wrong
except NameError:  # safety net
    dupes = len(stored) - len(set(stored))
    wrong = [p for p, cost in latest.items() if stored.get(p) != cost]
print(f"{len(stored)} prices stored | duplicates: {dupes} | not the latest version: {len(wrong)}")
Q.check(dupes == 0 and not wrong and len(stored) == 102, "merge: one row per price, every correction applied")

# %% [markdown]
# 🔍 Lab 2.1 kept every version in raw; this merge keeps only the latest. Both are right for different layers. Which
# would you choose for Qafila's raw layer, and what would you lose with the other?

# %% [markdown]
# ## ✱ Stretch · Freeze the schema
#
# A schema contract tells dlt what to do with a new column: `evolve` (the default), `freeze` (fail the load),
# `discard_value` or `discard_row`. Freeze the columns and feed one record with an unknown field.

# %%
# BEGIN SOLUTION
from dlt.pipeline.exceptions import PipelineStepFailed

frozen = dlt.resource([{"price_id": "PR-99999", "cost": "1.00", "updated_at": "2026-11-02T06:00:00+03:00",
                        "payment_terms": "60 days"}],
                      name="supplier_prices", primary_key="price_id", write_disposition="merge",
                      schema_contract={"columns": "freeze"})
try:
    new_pipeline().run(frozen)
    print("loaded: the contract did not hold")
except PipelineStepFailed as e:
    print("refused:", type(e.__context__ or e).__name__)
Q.check(count("SELECT count(*) FROM raw_suppliers.supplier_prices WHERE price_id = 'PR-99999'") == 0, "the frozen schema kept the record out")
# END SOLUTION

# %% [markdown]
# ## Checkpoint
#
# 1. The supplier adds a column. What should the pipeline do?
#    <details><summary>Answer</summary>Depends on the layer: raw evolves and records the change (nothing is lost);
#    a contract on the curated layer may freeze and alert, so a downstream model does not change meaning silently.
#    Lab 3.3 writes that contract.</details>
# 2. Where does dlt keep the cursor, and why there?
#    <details><summary>Answer</summary>In the destination (<code>_dlt_pipeline_state</code>), so a fresh machine
#    resumes from the data's own state, as Lab 2.1 did by hand.</details>
# 3. `merge` on `price_id` against `append` with a key on `(price_id, updated_at)`: which keeps history?
#    <details><summary>Answer</summary>The append. Merge keeps the latest version only; history then needs a type 2
#    table (Lab 2.3) or the raw versions.</details>
#
# **Carry forward.** Lab 2.4 cleans these prices; it starts from the source file, not from this database.
