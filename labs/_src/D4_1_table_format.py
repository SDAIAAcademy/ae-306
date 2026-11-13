# %% [markdown]
# # Lab 4.1 · The mart as an Iceberg table
#
# Day 4 · Session 1 (Open table formats) · 25 min. Finance's BI tool and Dalia's notebook should read the same margin
# table without copying it. In this lab you write the margin mart (order-line grain) as an Apache Iceberg table
# partitioned by month, walk its metadata on disk, add a column, append October, and read the current snapshot and
# an earlier one from a second engine, DuckDB, with identical results.
#
# **Reference state.** `Q.mart_table()`: the margin mart of Day 3 as an Arrow table, built from the reference models
# (17,665 lines with month, city, customer type, category, supplier country, revenue, cost, margin, freight).
# Nothing from another lab is needed. DuckDB downloads its `iceberg` extension on first use.
#
# **Tasks**
# - [ ] 1 · Create the table and its partition spec (6')
# - [ ] 2 · Walk the metadata on disk (4')
# - [ ] 3 · Evolve the schema and append (6')
# - [ ] 4 · Two engines, two snapshots (9')
# - [ ] ✱ Stretch · Expire old snapshots and see which files go

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

import pyarrow as pa
import pyarrow.compute as pc
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.partitioning import PartitionField, PartitionSpec
from pyiceberg.transforms import MonthTransform

mart = Q.mart_table()
mart = mart.cast(pa.schema([pa.field(f.name, pa.float64() if pa.types.is_decimal(f.type) else f.type) for f in mart.schema]))
WH = Q.lab_dir("D4_1")
catalog = SqlCatalog("qafila", uri=f"sqlite:///{Q.posix(WH)}/catalog.db", warehouse=Q.posix(WH))
catalog.create_namespace("mart")
TABLE_DIR = WH / "mart" / "margin_lines"
before_oct = mart.filter(pc.less(mart["month"], "2026-10")).drop_columns(["freight"])
october = mart.filter(pc.equal(mart["month"], "2026-10"))
print(f"{before_oct.num_rows:,} lines for August and September, {october.num_rows:,} for October")

# %% [markdown]
# ## 1 · Create the table and its partition spec (6')
#
# An Iceberg table is data files plus metadata files, registered in a **catalogue** (here a SQLite file; in
# production a REST catalogue, Glue, Polaris or Nessie). The partition spec says how rows are grouped into files:
# `month(order_date)` is a **hidden partition**, derived from a column, so queries filter on `order_date` and never
# need to know.
#
# ✏️ **Exercise** · Create `mart.margin_lines` with the schema of `before_oct` and a partition spec
# `month(order_date)`, then append `before_oct`. Keep the table in `table`.

# %%
# BEGIN SOLUTION
table = catalog.create_table("mart.margin_lines", schema=before_oct.schema)
with table.update_spec() as spec:
    spec.add_field("order_date", MonthTransform(), "order_month")
table.append(before_oct)
# END SOLUTION

# %%
try:
    table
except NameError:  # safety net
    table = catalog.create_table("mart.margin_lines", schema=before_oct.schema)
    with table.update_spec() as spec:
        spec.add_field("order_date", MonthTransform(), "order_month")
    table.append(before_oct)
table = catalog.load_table("mart.margin_lines")
print(table.spec())
first_snapshot = table.current_snapshot().snapshot_id
print("snapshot", first_snapshot, "| rows", table.scan().to_arrow().num_rows)
Q.check(table.scan().to_arrow().num_rows == before_oct.num_rows, "August and September are in the table")

# %% [markdown]
# ## 2 · Walk the metadata on disk (4')

# %%
for p in sorted((TABLE_DIR).rglob("*")):
    if p.is_file():
        print(f"{Q.mb(p.stat().st_size):>9s}  {p.relative_to(WH).as_posix()}")
files = table.inspect.files().to_pandas()
print(files[["record_count", "file_size_in_bytes"]].assign(partition=files.partition.astype(str)).to_string(index=False))
Q.check(len(files) == 2, "one data file per month: the partition spec at work")

# %% [markdown]
# 🔍 Three layers: `metadata/*.metadata.json` (schema, partition spec, the list of snapshots), the manifest list and
# manifests (`*.avro`: which data files, with per-column statistics) and the data files (Parquet, one folder per
# partition). A reader starts from the catalogue's pointer to the current metadata file.

# %% [markdown]
# ## 3 · Evolve the schema and append (6')
#
# In October finance adds freight to the mart. Iceberg changes the schema in metadata only: no file is rewritten,
# and columns are tracked by id, so a rename never confuses old files.
#
# ✏️ **Exercise** · Add the column `freight` (double, optional) with `table.update_schema()`, append `october`, and
# keep the snapshot id after the append in `second_snapshot`.

# %%
# BEGIN SOLUTION
with table.update_schema() as update:
    update.union_by_name(october.schema)
table.append(october)
second_snapshot = table.current_snapshot().snapshot_id
# END SOLUTION

# %%
try:
    second_snapshot
except NameError:  # safety net
    with table.update_schema() as update:
        update.union_by_name(october.schema)
    table.append(october)
    second_snapshot = table.current_snapshot().snapshot_id
print(table.schema())
print(table.inspect.snapshots().to_pandas()[["snapshot_id", "operation"]].to_string(index=False))
old_files_untouched = set(files.file_path) <= set(table.inspect.files().to_pandas().file_path)
Q.check(old_files_untouched, "adding a column rewrote no data file")

# %% [markdown]
# ## 4 · Two engines, two snapshots (9')
#
# DuckDB reads Iceberg with its `iceberg` extension, from the table's current metadata file. Time travel reads an
# earlier snapshot by id.
#
# ✏️ **Exercise** · Write `margin_by_month(engine, snapshot_id)`: monthly revenue, cost and margin from PyIceberg
# (`table.scan(snapshot_id=...)`) when `engine == "pyiceberg"`, or from DuckDB (`iceberg_scan(metadata,
# snapshot_from_id = ...)`) when `engine == "duckdb"`, as a list of `(month, revenue, cost, margin)` rounded to 2.

# %%
import duckdb

duck = duckdb.connect()
duck.execute("INSTALL iceberg")
duck.execute("LOAD iceberg")
METADATA = table.metadata_location.split("://", 1)[-1]        # a plain path for DuckDB
if len(METADATA) > 2 and METADATA[0] == "/" and METADATA[2] == ":":
    METADATA = METADATA[1:]                                         # Windows: drop the slash before the drive letter


def margin_by_month(engine: str, snapshot_id: int) -> list[tuple]:
    # BEGIN SOLUTION
    if engine == "pyiceberg":
        t = table.scan(snapshot_id=snapshot_id).to_arrow()
        return duck.sql("""SELECT month, round(sum(revenue), 2), round(sum(cost), 2), round(sum(margin), 2)
                           FROM t GROUP BY 1 ORDER BY 1""").fetchall()
    return duck.execute(f"""SELECT month, round(sum(revenue), 2), round(sum(cost), 2), round(sum(margin), 2)
                            FROM iceberg_scan('{METADATA}', snapshot_from_id = {snapshot_id}) GROUP BY 1 ORDER BY 1""").fetchall()
    # END SOLUTION


# %%
results = {}
for engine in ("pyiceberg", "duckdb"):
    for name, sid in (("current", second_snapshot), ("first", first_snapshot)):
        try:
            results[(engine, name)] = margin_by_month(engine, sid)
        except NotImplementedError:  # safety net
            t = table.scan(snapshot_id=sid).to_arrow()
            results[(engine, name)] = duck.sql("SELECT month, round(sum(revenue), 2), round(sum(cost), 2), round(sum(margin), 2) FROM t GROUP BY 1 ORDER BY 1").fetchall()
for k, v in results.items():
    print(k, v)
ref = {r["month"]: r["margin"] for r in Q.reference("finance_answers")["q1_monthly"]}
Q.check(results[("pyiceberg", "current")] == results[("duckdb", "current")], "both engines agree on the current snapshot")
Q.check(results[("pyiceberg", "first")] == results[("duckdb", "first")] and len(results[("duckdb", "first")]) == 2,
        "both engines agree on the first snapshot, which has no October")
Q.check(all(abs(m - ref[mo]) < 1 for mo, _, _, m in results[("duckdb", "current")]), "the current snapshot equals finance's reference")
print(duck.execute(f"SELECT count(*) FROM iceberg_scan('{METADATA}') WHERE order_date BETWEEN DATE '2026-09-01' AND DATE '2026-09-30'").fetchall())

# %% [markdown]
# ## ✱ Stretch · Expire old snapshots
#
# Time travel keeps old files alive. Expiring a snapshot lets its unreferenced files be deleted. Overwrite August
# (a correction), then expire the snapshots before it and count the data files before and after.

# %%
# BEGIN SOLUTION
august = table.scan(row_filter="order_date < '2026-09-01'").to_arrow()
table.overwrite(august, overwrite_filter="order_date < '2026-09-01'")
print(table.inspect.snapshots().to_pandas()[["snapshot_id", "operation"]].to_string(index=False))
n_files_before = sum(1 for p in (TABLE_DIR / "data").rglob("*.parquet"))
try:
    table.maintenance.expire_snapshots().by_ids([first_snapshot]).commit()
    print("expired", first_snapshot, "| snapshots now:", len(table.inspect.snapshots()))
except Exception as e:  # noqa: BLE001 - the maintenance API is recent and changes between releases
    print("expire not available in this PyIceberg:", type(e).__name__, str(e)[:100])
print("data files on disk:", n_files_before, "(PyIceberg expires metadata; deleting orphan files is a separate step)")
# END SOLUTION

# %% [markdown]
# ## Checkpoint
#
# 1. An analyst renames `cost` to `unit_cost` in the Iceberg table. What happens to the old data files?
#    <details><summary>Answer</summary>Nothing: the rename is a metadata change. Columns are matched by id, not by
#    name, so old files read correctly under the new name.</details>
# 2. Why is `month(order_date)` better than a separate `month` column for partitioning?
#    <details><summary>Answer</summary>Queries filter on <code>order_date</code> and still prune: the table knows how
#    the partition is derived (hidden partitioning). Lab 1.4's folders needed the filter on the partition column.</details>
# 3. What makes the second engine's answer identical?
#    <details><summary>Answer</summary>Both read the same snapshot: the same metadata file lists the same data files.
#    No copy, no export.</details>
#
# **Carry forward.** The capstone writes its mart the same way.
