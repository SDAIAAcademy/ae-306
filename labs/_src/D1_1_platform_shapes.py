# %% [markdown]
# # Lab 1.1 · Ten workloads, three layers
#
# Day 1 · Session 1 (Platform shapes) · 25 min. Qafila's order database answers the sales app in milliseconds,
# and finance wants it to answer the monthly margin too. In this lab you time one point lookup and one monthly
# aggregate on a row store (SQLite) and a column store (DuckDB), then place ten Qafila workloads in the
# transactional, warehouse or lakehouse layer and justify each one in a sentence.
#
# **AI-tutor.** An AI assistant may give hints in this lab; it does not write your queries, models or tests.
#
# **Reference state.** `data/raw/qafila_orders.sqlite` (the order database) and `data/raw/extracts/` (its nightly
# extracts), both written by `qafila_data.py` with seed 306. Nothing from another lab is needed.
#
# **Tasks**
# - [ ] 1 · Open the order database and the extracts (4')
# - [ ] 2 · A point lookup and an aggregate, in both engines (7')
# - [ ] 3 · Place ten workloads, with a reason each (10')
# - [ ] 4 · Compare with the key and defend one difference (4')
# - [ ] ✱ Stretch · Where would a nightly copy of the order database live, and why?

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
Q.ensure_data()
print("quick mode:", Q.QUICK)

# %% [markdown]
# ## 1 · Open the order database and the extracts (4')
#
# The order database is what the sales app writes to. The extracts are what the nightly job copies out of it.

# %%
import sqlite3
import duckdb

oltp = sqlite3.connect(Q.RAW / "qafila_orders.sqlite")
for t in ["customers", "products", "orders", "order_lines"]:
    print(f"{t:12s}", oltp.execute(f"SELECT count(*) FROM {t}").fetchall()[0][0], "rows")
print("indexes:", [r[0] for r in oltp.execute("SELECT name FROM sqlite_master WHERE type = 'index'")])

con = Q.warehouse()
print("extract lines:", con.execute("SELECT count(*) FROM raw.order_lines").fetchall()[0][0])

# %% [markdown]
# 🔍 The database has 18,403 order lines and the extract 18,630. Keep that difference in mind: Lab 1.2 explains it.

# %% [markdown]
# ## 2 · A point lookup and an aggregate, in both engines (7')
#
# To make the difference visible, both engines get the same order lines repeated `SCALE` times (new order ids
# each time). SQLite keeps rows together with an index on `order_id`; DuckDB keeps columns together.
#
# ✏️ **Exercise** · Write the two queries as strings, in SQL that both engines accept:
# - `POINT`: every line of order `50001` (the sales app opening one order),
# - `AGG`: revenue per month for confirmed orders, `qty * unit_price_sar * (1 - discount_pct / 100)`, with the month
#   as `substr(order_date, 1, 7)`.

# %%
SCALE = Q.pick(30, 5)
big_sqlite = sqlite3.connect(":memory:")
oltp.backup(big_sqlite)
big_sqlite.executescript(f"""
    CREATE TABLE ol AS SELECT * FROM order_lines WHERE 0;
    CREATE TABLE o AS SELECT * FROM orders WHERE 0;
    WITH RECURSIVE k(i) AS (SELECT 0 UNION ALL SELECT i + 1 FROM k WHERE i < {SCALE} - 1)
    INSERT INTO ol SELECT order_id + i * 1000000, line_no, product_id, unit, qty, unit_price_sar, discount_pct FROM order_lines, k;
    WITH RECURSIVE k(i) AS (SELECT 0 UNION ALL SELECT i + 1 FROM k WHERE i < {SCALE} - 1)
    INSERT INTO o SELECT order_id + i * 1000000, customer_id, order_date, status, created_at, updated_at FROM orders, k;
    CREATE INDEX ix_ol ON ol(order_id);
    CREATE UNIQUE INDEX ix_o ON o(order_id);
""")
import pandas as pd

cols_ol = ["order_id", "line_no", "product_id", "unit", "qty", "unit_price_sar", "discount_pct"]
cols_o = ["order_id", "customer_id", "order_date", "status", "created_at", "updated_at"]
olap = duckdb.connect()
ol_df = pd.DataFrame(big_sqlite.execute("SELECT * FROM ol").fetchall(), columns=cols_ol)
o_df = pd.DataFrame(big_sqlite.execute("SELECT * FROM o").fetchall(), columns=cols_o)
olap.execute("CREATE TABLE ol AS SELECT * FROM ol_df")
olap.execute("CREATE TABLE o AS SELECT * FROM o_df")
print(f"{len(ol_df):,} lines and {len(o_df):,} orders in each engine")

# BEGIN SOLUTION
POINT = "SELECT * FROM ol WHERE order_id = 50001 ORDER BY line_no"
AGG = """
    SELECT substr(o.order_date, 1, 7) AS month,
           round(sum(ol.qty * ol.unit_price_sar * (1 - ol.discount_pct / 100.0)), 2) AS revenue
    FROM ol JOIN o USING (order_id)
    WHERE o.status = 'confirmed'
    GROUP BY 1 ORDER BY 1"""
# END SOLUTION

# %%
# Check, with a safety net: the cells below still run when the exercise is not done yet
try:
    POINT, AGG
except NameError:
    POINT = "SELECT * FROM ol WHERE order_id = 50001 ORDER BY line_no"
    AGG = ("SELECT substr(o.order_date, 1, 7) AS month, round(sum(ol.qty * ol.unit_price_sar * (1 - ol.discount_pct / 100.0)), 2) "
           "AS revenue FROM ol JOIN o USING (order_id) WHERE o.status = 'confirmed' GROUP BY 1 ORDER BY 1")
timings = {}
for engine, run in [("SQLite (rows)", lambda q: big_sqlite.execute(q).fetchall()),
                    ("DuckDB (columns)", lambda q: olap.execute(q).fetchall())]:
    t_point, point_rows = Q.timed(lambda: run(POINT), repeat=5)
    t_agg, agg_rows = Q.timed(lambda: run(AGG), repeat=3)
    timings[engine] = {"point lookup (ms)": round(1000 * t_point, 2), "monthly aggregate (ms)": round(1000 * t_agg, 1)}
    Q.check(len(point_rows) == 6 and len(agg_rows) == 3, f"{engine}: {len(point_rows)} lines of order 50001, {len(agg_rows)} months")
print(pd.DataFrame(timings).T)

# %% [markdown]
# 🔍 Read the table. Which engine wins the lookup, and by how much does the other win the aggregate? The numbers
# change with your machine; the direction should not.

# %% [markdown]
# ## 3 · Place ten workloads, with a reason each (10')
#
# Three layers: **transactional** (the order database: small reads and writes by key while someone waits),
# **warehouse** (modelled, tested tables for analysis in a column store), **lakehouse** (open files and open tables
# that keep raw history and serve more than one engine).
#
# ✏️ **Exercise** · Fill `placement` with one entry per workload: `"W01": ("transactional", "your reason")`.
# Reason from the access pattern: how many rows, read or write, who waits, how many engines read it.

# %%
import json

W = json.loads((Q.REF / "workloads.json").read_text(encoding="utf-8"))
for wid, text in W["workloads"].items():
    print(wid, text)

# %%
# BEGIN SOLUTION
placement = {
    "W01": ("transactional", "one order written while the salesperson waits"),
    "W02": ("transactional", "a lookup by customer key on current data, inside the order flow"),
    "W03": ("warehouse", "a scan and aggregate over three months of lines"),
    "W04": ("lakehouse", "raw files kept as received for audit and replay"),
    "W05": ("transactional", "small concurrent updates by key"),
    "W06": ("warehouse", "one modelled, tested dimension that several reports share"),
    "W07": ("lakehouse", "large history in open files, read by other teams' engines"),
    "W08": ("warehouse", "a window over the price history, refreshed nightly"),
    "W09": ("transactional", "one row updated by key from the driver's app"),
    "W10": ("lakehouse", "an open table read by two engines"),
}
# END SOLUTION

# %%
try:
    placement
except NameError:
    placement = {w: (k[0], "(safety net: the key)") for w, k in W["key"].items()}
Q.check(set(placement) == set(W["workloads"]), "ten workloads placed")
Q.check(all(p[0] in W["layers"] and len(p[1]) > 10 for p in placement.values()), "every placement has a layer and a reason")

# %% [markdown]
# ## 4 · Compare with the key and defend one difference (4')
#
# The key is one defensible answer, not the only one. Where you differ, the reason is what counts.

# %%
rows = [{"workload": w, "yours": placement[w][0], "key": k[0], "same": placement[w][0] == k[0], "key's reason": k[1]}
        for w, k in W["key"].items()]
cmp = pd.DataFrame(rows)
print(cmp.to_string(index=False))
print(f"\nagreement: {cmp.same.sum()} of {len(cmp)}")

# %% [markdown]
# ✏️ Write two sentences in the cell below for one workload where you differ from the key, or for W08 if you
# agree on all ten: which layer, and what would have to change in the workload for the other layer to be right.

# %% [markdown]
# *Your answer here.*

# %% [markdown]
# ## ✱ Stretch · A nightly copy of the order database
#
# Where would you keep a nightly copy of `qafila_orders.sqlite`? Measure what the copy costs as files.

# %%
# BEGIN SOLUTION
snap = Q.lab_dir("D1_1")
for t in ["orders", "order_lines", "customers", "products"]:
    con.execute(f"COPY (SELECT * FROM raw.{t}) TO '{Q.posix(snap)}/{t}.parquet' (FORMAT parquet)")
print("SQLite file:", Q.mb((Q.RAW / "qafila_orders.sqlite").stat().st_size), "| Parquet copy:", Q.mb(Q.folder_bytes(snap)))
print("The raw layer of the lakehouse: a dated, unchanged copy that any engine can read and that can be replayed.")
# END SOLUTION

# %% [markdown]
# ## Checkpoint
#
# 1. Finance's dashboard runs the monthly aggregate on the order database every five minutes. What breaks first?
#    <details><summary>Answer</summary>The order flow: long scans compete with the sales app's short writes and
#    lock or slow them. The aggregate belongs on a copy in a column store.</details>
# 2. Why did the row store win the point lookup?
#    <details><summary>Answer</summary>An index on <code>order_id</code> leads to the few rows, and each row is stored
#    together: one read returns the whole line.</details>
# 3. What makes a workload "lakehouse" rather than "warehouse"?
#    <details><summary>Answer</summary>Open files or open tables that keep raw history cheaply and are read by more
#    than one engine; a warehouse table is read through one engine.</details>
#
# **Carry forward.** Nothing: Lab 1.2 starts from the extracts again.
