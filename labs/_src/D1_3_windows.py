# %% [markdown]
# # Lab 1.3 · Running margin, price changes, first and last orders
#
# Day 1 · Session 3 (Window functions) · 25 min. Finance wants the margin to date inside each month, procurement
# wants every supplier price change and its size, and sales wants each customer's first and last order. All three
# keep the rows and add a value computed over neighbouring rows: window functions.
#
# **AI-tutor.** An AI assistant may give hints in this lab; it does not write your queries, models or tests.
#
# **Reference state.** `Q.warehouse()` loads the extracts and `Q.build_models(con)` builds the cleaned tables
# (`stg.*`) and the order-line fact (`mart.fct_order_line`, confirmed orders, one copy per line, cost at the price
# valid on the order date): the result of Lab 1.2, supplied.
#
# **Tasks**
# - [ ] 1 · GROUP BY against OVER on one week (4')
# - [ ] 2 · Running margin that restarts each month (6')
# - [ ] 3 · Supplier price changes with LAG (7')
# - [ ] 4 · First and last order per customer (8')
# - [ ] ✱ Stretch · ROW_NUMBER, RANK and DENSE_RANK on a tie

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

con = Q.warehouse()
print("built:", Q.build_models(con))

# %% [markdown]
# ## 1 · GROUP BY against OVER on one week (4')
#
# `GROUP BY` returns one row per group. `OVER (PARTITION BY ...)` returns every row with the group's value beside it.

# %%
week = "order_date BETWEEN DATE '2026-09-06' AND DATE '2026-09-12'"
by_day = con.sql(f"SELECT order_date, round(sum(revenue), 2) AS day_revenue FROM mart.fct_order_line WHERE {week} GROUP BY 1 ORDER BY 1").df()
print(by_day.to_string(index=False), "\n", len(by_day), "rows")

# %% [markdown]
# ✏️ **Exercise** · Write `SHARE_SQL`: every line of that week with its `revenue`, the `day_revenue` of its day (a
# window, not a join) and `share_pct`, the line's share of its day in percent.

# %%
# BEGIN SOLUTION
SHARE_SQL = f"""
SELECT order_id, line_no, order_date, revenue,
       sum(revenue) OVER (PARTITION BY order_date) AS day_revenue,
       round(100 * revenue / sum(revenue) OVER (PARTITION BY order_date), 3) AS share_pct
FROM mart.fct_order_line WHERE {week}"""
# END SOLUTION

# %%
try:
    share = con.sql(SHARE_SQL).df()
except NameError:
    share = con.sql(f"SELECT order_id, line_no, order_date, revenue, sum(revenue) OVER (PARTITION BY order_date) AS day_revenue, "
                    f"round(100 * revenue / sum(revenue) OVER (PARTITION BY order_date), 3) AS share_pct FROM mart.fct_order_line WHERE {week}").df()
n_week = con.execute(f"SELECT count(*) FROM mart.fct_order_line WHERE {week}").fetchall()[0][0]
Q.check(len(share) == n_week, f"{len(share):,} lines kept, not {len(by_day)} rows")
Q.check(abs(share.groupby("order_date").share_pct.sum() - 100).max() < 0.1, "each day's shares add up to 100")

# %% [markdown]
# ## 2 · Running margin that restarts each month (6')
#
# ✏️ **Exercise** · From the daily margin (`daily`, given), write `RUNNING_SQL` with `margin_to_date`: the margin
# from the first day of the month to this day. The running total must restart on the first of each month.

# %%
con.execute("""CREATE OR REPLACE TABLE daily AS
    SELECT order_date, strftime(order_date, '%Y-%m') AS month, sum(revenue - cost) AS margin
    FROM mart.fct_order_line GROUP BY 1, 2""")

# BEGIN SOLUTION
RUNNING_SQL = """
SELECT order_date, month, round(margin, 2) AS margin,
       round(sum(margin) OVER (PARTITION BY month ORDER BY order_date
                               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2) AS margin_to_date
FROM daily ORDER BY order_date"""
# END SOLUTION

# %%
try:
    running = con.sql(RUNNING_SQL).df()
except NameError:
    running = con.sql("SELECT order_date, month, round(margin, 2) AS margin, round(sum(margin) OVER (PARTITION BY month "
                      "ORDER BY order_date), 2) AS margin_to_date FROM daily ORDER BY order_date").df()
print(running.head(3).to_string(index=False), "\n...\n", running[running.order_date.astype(str).str.endswith(("-01", "-02"))].to_string(index=False))
month_end = running.groupby("month").margin_to_date.last()
reference = Q.reference("finance_answers")["q1_monthly"]
Q.check(all(abs(month_end[r["month"]] - r["margin"]) < 1 for r in reference), "the last day of each month equals finance's monthly margin")
Q.check(running.iloc[running.month.ne(running.month.shift()).to_numpy().nonzero()[0]].eval("margin == margin_to_date").all(),
        "the running total restarts on the first day of each month")

# %% [markdown]
# ## 3 · Supplier price changes with LAG (7')
#
# `stg.prices` has one row per price version: `product_id`, `supplier_id`, `cost_piece_sar`, `valid_from`.
#
# ✏️ **Exercise** · Write `CHANGES_SQL`: one row per price change (not the first price of a product), with the
# previous cost (`LAG` over the product's versions in date order), `change_pct`, and the product and supplier.
# Order by the size of the change, largest first.

# %%
# BEGIN SOLUTION
CHANGES_SQL = """
WITH v AS (
  SELECT product_id, supplier_id, valid_from, cost_piece_sar,
         lag(cost_piece_sar) OVER (PARTITION BY product_id ORDER BY valid_from) AS previous_cost
  FROM stg.prices)
SELECT product_id, supplier_id, valid_from, previous_cost, cost_piece_sar,
       round(100 * (cost_piece_sar - previous_cost) / previous_cost, 1) AS change_pct
FROM v WHERE previous_cost IS NOT NULL
ORDER BY abs(change_pct) DESC"""
# END SOLUTION

# %%
try:
    changes = con.sql(CHANGES_SQL).df()
except NameError:
    changes = con.sql("WITH v AS (SELECT *, lag(cost_piece_sar) OVER (PARTITION BY product_id ORDER BY valid_from) AS previous_cost FROM stg.prices) "
                      "SELECT product_id, supplier_id, valid_from, previous_cost, cost_piece_sar, round(100 * (cost_piece_sar - previous_cost) / previous_cost, 1) "
                      "AS change_pct FROM v WHERE previous_cost IS NOT NULL ORDER BY abs(change_pct) DESC").df()
versions = con.execute("SELECT count(*), count(DISTINCT product_id) FROM stg.prices").fetchall()[0]
print(changes.head(8).to_string(index=False))
Q.check(len(changes) == versions[0] - versions[1], f"{len(changes)} changes = {versions[0]} versions minus {versions[1]} first prices")
print("changes above 5 percent:", int((changes.change_pct.abs() > 5).sum()))

# %% [markdown]
# ## 4 · First and last order per customer (8')
#
# ✏️ **Exercise** · Write `FIRST_LAST_SQL`: one row per customer with `first_order_date`, `first_order_id`,
# `last_order_date`, `last_order_id` and `orders`, from `stg.orders` (confirmed only). Use `row_number()` twice
# (ascending and descending) and `QUALIFY`, or `arg_min` / `arg_max`.

# %%
# BEGIN SOLUTION
FIRST_LAST_SQL = """
WITH o AS (
  SELECT customer_id, order_id, created_at,
         row_number() OVER (PARTITION BY customer_id ORDER BY created_at, order_id) AS n_first,
         row_number() OVER (PARTITION BY customer_id ORDER BY created_at DESC, order_id DESC) AS n_last,
         count(*) OVER (PARTITION BY customer_id) AS orders
  FROM stg.orders WHERE status = 'confirmed')
SELECT customer_id,
       max(CAST(created_at AS DATE)) FILTER (WHERE n_first = 1) AS first_order_date, max(order_id) FILTER (WHERE n_first = 1) AS first_order_id,
       max(CAST(created_at AS DATE)) FILTER (WHERE n_last = 1) AS last_order_date, max(order_id) FILTER (WHERE n_last = 1) AS last_order_id,
       any_value(orders) AS orders
FROM o WHERE n_first = 1 OR n_last = 1
GROUP BY customer_id ORDER BY customer_id"""
# END SOLUTION

# %%
try:
    first_last = con.sql(FIRST_LAST_SQL).df()
except NameError:
    first_last = con.sql("""SELECT customer_id, CAST(min(created_at) AS DATE) AS first_order_date, arg_min(order_id, created_at) AS first_order_id,
        CAST(max(created_at) AS DATE) AS last_order_date, arg_max(order_id, created_at) AS last_order_id, count(*) AS orders
        FROM stg.orders WHERE status = 'confirmed' GROUP BY 1 ORDER BY 1""").df()
check = con.sql("""SELECT customer_id, arg_min(order_id, created_at) AS f, arg_max(order_id, created_at) AS l
                   FROM stg.orders WHERE status = 'confirmed' GROUP BY 1 ORDER BY 1""").df()
print(first_last.head(5).to_string(index=False))
Q.check(len(first_last) == len(check), f"{len(first_last)} customers with confirmed orders, one row each")
Q.check((first_last.first_order_id.values == check.f.values).all() and (first_last.last_order_id.values == check.l.values).all(),
        "first and last order ids agree with arg_min and arg_max")
print("customers whose last order is before October:", int((first_last.last_order_date.astype(str) < "2026-10-01").sum()))

# %% [markdown]
# 🔍 One customer id in the list is not in `stg.customers`. Which one, and why? (Day 3 and Day 4 come back to it.)

# %%
print(con.sql("SELECT customer_id, orders FROM first_last WHERE customer_id NOT IN (SELECT customer_id FROM stg.customers)"))

# %% [markdown]
# ## ✱ Stretch · ROW_NUMBER, RANK and DENSE_RANK on a tie
#
# Rank customers by number of confirmed orders. Where two customers tie, what does each function give?

# %%
# BEGIN SOLUTION
print(con.sql("""
    SELECT customer_id, orders,
           row_number() OVER (ORDER BY orders DESC, customer_id) AS row_number,
           rank() OVER (ORDER BY orders DESC) AS rank,
           dense_rank() OVER (ORDER BY orders DESC) AS dense_rank
    FROM first_last ORDER BY orders DESC, customer_id LIMIT 10"""))
# END SOLUTION

# %% [markdown]
# ## Checkpoint
#
# 1. A running total must restart each month. Which `PARTITION BY` and which `ORDER BY`?
#    <details><summary>Answer</summary><code>PARTITION BY month ORDER BY order_date</code>: the partition says where
#    the total restarts, the order says what "so far" means.</details>
# 2. Why can't you write `WHERE row_number() OVER (...) = 1`?
#    <details><summary>Answer</summary>Windows are computed after <code>WHERE</code>. Filter in an outer query or
#    with <code>QUALIFY</code>, which runs after the windows.</details>
# 3. Two price versions of one product share a `valid_from`. What does `LAG` return, and why is that a problem?
#    <details><summary>Answer</summary>An arbitrary order between the two: the "previous" price is not defined.
#    Add a tie-breaker to the window's <code>ORDER BY</code>, or fix the duplicate version at the source.</details>
#
# **Carry forward.** The price-change query becomes procurement's daily list (workload W08 of Lab 1.1).
