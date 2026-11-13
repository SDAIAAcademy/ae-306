# %% [markdown]
# # Lab 1.2 · Reproduce the monthly margin
#
# Day 1 · Session 2 (Analytical SQL on a single node) · 25 min. Lujain Al-Zamil, Qafila's finance controller, has
# two numbers for August: the margin report everyone uses and a reference she computed by hand from confirmed
# orders. They differ. In this lab you query the raw extracts **in place** with DuckDB, compute revenue and cost per
# line with the price valid on the order date, reproduce her reference and write down the two defects that explain
# the gap.
#
# **AI-off.** This lab is done without an AI assistant: the evidence for this outcome is *your* queries and
# *your* note.
#
# **Reference state.** `data/raw/extracts/*.csv` and `data/reference/monthly_margin.csv` (finance's reference),
# `data/reference/margin_report_old.csv` (the report nobody trusts).
#
# **Tasks**
# - [ ] 1 · Read the extracts in place and profile them (5')
# - [ ] 2 · Revenue and cost per line, with the price valid on the order date (8')
# - [ ] 3 · The monthly margin against finance's reference (6')
# - [ ] 4 · Find the two defects and write the note (6')
# - [ ] ✱ Stretch · An incremental predicate: recompute only the month that changed

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

# %% [markdown]
# ## 1 · Read the extracts in place and profile them (5')
#
# DuckDB reads a CSV file as if it were a table: no load step. `E` is the folder of the extracts.

# %%
import duckdb
import pandas as pd

con = duckdb.connect()
E = Q.posix(Q.EXTRACTS)
print(con.sql(f"SELECT * FROM read_csv('{E}/order_lines.csv') LIMIT 3"))
print(con.sql(f"SUMMARIZE SELECT * FROM read_csv('{E}/orders.csv')").select("column_name", "column_type", "approx_unique", "null_percentage"))

# %% [markdown]
# ✏️ **Exercise** · Profile the two things a margin depends on. Write `PROFILE_STATUS` (orders per `status`) and
# `PROFILE_KEYS` (the number of order lines and the number of distinct `(order_id, line_no)` pairs in
# `order_lines.csv`).

# %%
# BEGIN SOLUTION
PROFILE_STATUS = f"SELECT status, count(*) AS orders FROM read_csv('{E}/orders.csv') GROUP BY ALL ORDER BY orders DESC"
PROFILE_KEYS = f"""SELECT count(*) AS lines, count(DISTINCT (order_id, line_no)) AS distinct_keys
                   FROM read_csv('{E}/order_lines.csv')"""
# END SOLUTION

# %%
try:
    status = con.sql(PROFILE_STATUS).df()
    keys = con.sql(PROFILE_KEYS).df()
except NameError:
    status = con.sql(f"SELECT status, count(*) AS orders FROM read_csv('{E}/orders.csv') GROUP BY ALL").df()
    keys = con.sql(f"SELECT count(*) AS lines, count(DISTINCT (order_id, line_no)) AS distinct_keys FROM read_csv('{E}/order_lines.csv')").df()
print(status.to_string(index=False))
print(keys.to_string(index=False))
Q.check(int(keys.lines[0]) == 18630 and int(keys.distinct_keys[0]) == 18403, "18,630 lines but only 18,403 distinct keys")

# %% [markdown]
# 🔍 Two facts to keep: some orders are not `confirmed`, and some lines appear twice.

# %% [markdown]
# ## 2 · Revenue and cost per line, with the price valid on the order date (8')
#
# - Revenue: `qty * unit_price_sar * (1 - discount_pct / 100)`.
# - Cost: pieces times the ERP cost per piece **valid on the order date**. `prices.csv` has one row per price
#   version, `valid_from` to `valid_to` (inclusive; empty means still valid). A line in cartons has
#   `qty * units_per_carton` pieces (from `products.csv`).
#
# ✏️ **Exercise** · Write `LINE_SQL`: one row per extract line with `order_id`, `line_no`, `order_date`, `status`,
# `revenue` and `cost`. Keep every line for now (duplicates and every status): step 3 decides what to drop.

# %%
# BEGIN SOLUTION
LINE_SQL = f"""
SELECT l.order_id, l.line_no, o.order_date, o.status,
       l.qty * l.unit_price_sar * (1 - l.discount_pct / 100) AS revenue,
       l.qty * CASE WHEN l.unit = 'carton' THEN p.units_per_carton ELSE 1 END * pr.cost_piece_sar AS cost
FROM read_csv('{E}/order_lines.csv') AS l
JOIN read_csv('{E}/orders.csv') AS o USING (order_id)
JOIN read_csv('{E}/products.csv') AS p USING (product_id)
JOIN read_csv('{E}/prices.csv') AS pr
  ON pr.product_id = l.product_id
 AND o.order_date BETWEEN pr.valid_from AND coalesce(pr.valid_to, DATE '9999-12-31')
"""
# END SOLUTION

# %%
try:
    con.execute(f"CREATE OR REPLACE TABLE line_margin AS {LINE_SQL}")
except NameError:
    con.execute(f"""CREATE OR REPLACE TABLE line_margin AS
        SELECT l.order_id, l.line_no, o.order_date, o.status, l.qty * l.unit_price_sar * (1 - l.discount_pct / 100) AS revenue,
               l.qty * CASE WHEN l.unit = 'carton' THEN p.units_per_carton ELSE 1 END * pr.cost_piece_sar AS cost
        FROM read_csv('{E}/order_lines.csv') l JOIN read_csv('{E}/orders.csv') o USING (order_id)
        JOIN read_csv('{E}/products.csv') p USING (product_id) JOIN read_csv('{E}/prices.csv') pr
          ON pr.product_id = l.product_id AND o.order_date BETWEEN pr.valid_from AND coalesce(pr.valid_to, DATE '9999-12-31')""")
n = con.execute("SELECT count(*) FROM line_margin").fetchall()[0][0]
Q.check(n == 18630, f"{n:,} lines priced: every extract line found exactly one valid price")

# %% [markdown]
# 🔍 If you joined on `product_id` alone you would get more rows than lines: one per price version. Count them once
# to see the fan-out: `SELECT count(*) FROM order_lines JOIN prices USING (product_id)`.

# %% [markdown]
# ## 3 · The monthly margin against finance's reference (6')
#
# ✏️ **Exercise** · Write `monthly(sql_filter)`: a function that returns revenue, cost, margin and margin percent per
# month from `line_margin`, keeping the rows that pass `sql_filter` (a SQL condition such as `TRUE`). Then compare
# `monthly("TRUE")` with the old report and with the reference.

# %%
def monthly(sql_filter: str = "TRUE", table: str = "line_margin") -> pd.DataFrame:
    # BEGIN SOLUTION
    return con.sql(f"""
        SELECT strftime(order_date, '%Y-%m') AS month, round(sum(revenue), 2) AS revenue, round(sum(cost), 2) AS cost,
               round(sum(revenue) - sum(cost), 2) AS margin, round(100 * (sum(revenue) - sum(cost)) / sum(revenue), 2) AS margin_pct
        FROM {table} WHERE {sql_filter} GROUP BY 1 ORDER BY 1""").df()
    # END SOLUTION


# %%
reference = pd.read_csv(Q.REF / "monthly_margin.csv")
old = pd.read_csv(Q.REF / "margin_report_old.csv")
try:
    naive = monthly("TRUE")
except NotImplementedError:
    naive = old.copy()
print("everything in the extract:\n", naive.to_string(index=False))
print("\nthe old report:\n", old.to_string(index=False))
print("\nfinance's reference:\n", reference.to_string(index=False))
Q.check((naive.revenue - old.revenue).abs().max() < 1, "summing every extract line reproduces the old report")

# %% [markdown]
# ## 4 · Find the two defects and write the note (6')
#
# The naive query *is* the old report. Find the two filters that turn it into the reference, measure what each
# one is worth in August, and write the note.
#
# ✏️ **Exercise** · Build `clean_lines`: one row per `(order_id, line_no)` of a confirmed order (DuckDB's
# `QUALIFY row_number() OVER (...) = 1` keeps one copy). Then `monthly("TRUE", "clean_lines")` must match the
# reference to the riyal.

# %%
# BEGIN SOLUTION
con.execute("""CREATE OR REPLACE TABLE clean_lines AS
    SELECT * FROM line_margin WHERE status = 'confirmed'
    QUALIFY row_number() OVER (PARTITION BY order_id, line_no ORDER BY order_date) = 1""")
# END SOLUTION

# %%
try:
    fixed = monthly("TRUE", "clean_lines")
except Exception:  # noqa: BLE001 - safety net for a skipped exercise
    con.execute("CREATE OR REPLACE TABLE clean_lines AS SELECT * FROM line_margin WHERE status = 'confirmed' "
                "QUALIFY row_number() OVER (PARTITION BY order_id, line_no ORDER BY order_date) = 1")
    fixed = monthly("TRUE", "clean_lines")
print(fixed.to_string(index=False))
Q.check((fixed.revenue - reference.revenue).abs().max() < 1 and (fixed.cost - reference.cost).abs().max() < 1,
        "the clean lines reproduce finance's reference in every month (within one riyal of rounding)")

# What each defect is worth, per month: the revenue each one adds to the old report
worth = con.sql("""
    WITH tagged AS (
      SELECT *, row_number() OVER (PARTITION BY order_id, line_no ORDER BY order_date) > 1 AS is_copy FROM line_margin)
    SELECT strftime(order_date, '%Y-%m') AS month,
           round(sum(revenue) FILTER (WHERE status <> 'confirmed' AND NOT is_copy), 2) AS cancelled_orders,
           round(sum(revenue) FILTER (WHERE is_copy), 2) AS repeated_lines
    FROM tagged GROUP BY 1 ORDER BY 1""").df()
print(worth.to_string(index=False))
print(con.sql("""SELECT order_date, count(*) AS lines, count(DISTINCT (order_id, line_no)) AS distinct_lines
                 FROM line_margin GROUP BY 1 HAVING count(*) > count(DISTINCT (order_id, line_no))"""))

# %% [markdown]
# ✏️ **The note.** Two or three sentences each: what the defect is, where it is, what it is worth, and the rule that
# fixes it. This note is the evidence for outcome LO1.
#
# *Defect 1:* …
#
# *Defect 2:* …

# %% [markdown]
# ## ✱ Stretch · An incremental predicate
#
# A late correction arrives for October only. Recompute only October and append it to the stored months instead of
# rescanning everything. Compare how many rows each approach reads.

# %%
# BEGIN SOLUTION
store = monthly("TRUE", "clean_lines")
store = store[store.month < "2026-10"]
october = monthly("order_date >= DATE '2026-10-01'", "clean_lines")
store = pd.concat([store, october], ignore_index=True)
rows_all = con.execute("SELECT count(*) FROM clean_lines").fetchall()[0][0]
rows_oct = con.execute("SELECT count(*) FROM clean_lines WHERE order_date >= DATE '2026-10-01'").fetchall()[0][0]
print(store.to_string(index=False))
print(f"rows read: full {rows_all:,} | incremental {rows_oct:,}")
Q.check(store.equals(fixed), "the incremental result equals the full recompute")
# END SOLUTION

# %% [markdown]
# ## Checkpoint
#
# 1. Your August margin is above the reference. Which check do you run first, and why that one?
#    <details><summary>Answer</summary>Count rows against distinct keys at the grain you expect (one per order
#    line): a duplicate inflates revenue and cost together, so it is the cheapest gap to rule out.</details>
# 2. Why must the price join use the order date, not the latest price?
#    <details><summary>Answer</summary>Prices change inside the quarter; the latest price re-costs past orders at
#    today's price and moves last month's margin every time procurement updates a price.</details>
# 3. Why reproduce the reference before building anything on top of it?
#    <details><summary>Answer</summary>Until your number matches a trusted one, you do not know whether a later
#    difference comes from your pipeline or from your understanding of the data.</details>
#
# **Carry forward.** The two rules (one copy per order line; confirmed orders only) become the staging models of
# Day 3 (`models/stg_order_lines.sql`, `models/fct_order_line.sql`).
