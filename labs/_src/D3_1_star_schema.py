# %% [markdown]
# # Lab 3.1 · The margin star schema
#
# Day 3 · Session 1 (Dimensional modelling) · 25 min. Finance asks five questions of the margin every month. In
# this lab you state the grain, draw the star that answers them, build the dimensions (with an unknown member) and
# the fact table, test the grain, and check all five answers against finance's reference.
#
# **AI-tutor.** An AI assistant may give hints in this lab; it does not write your queries, models or tests.
#
# **Reference state.** `Q.warehouse()` and `Q.build_models(con, names=STAGING)`: the staging tables of Day 2
# (`stg.*`, typed and deduplicated) and the supplier history (`raw.supplier_history`, Lab 2.3's type 2 table).
#
# **Finance's five questions** (`data/reference/finance_answers.json`):
# 1. Monthly revenue, cost and margin. 2. Margin by customer type and city. 3. Margin by supplier country **at the
# time of the order**. 4. Margin by category and month. 5. Margin by city **after freight**.
#
# **Tasks**
# - [ ] 1 · Draw the star: grain, facts, dimensions (6')
# - [ ] 2 · Dimensions with an unknown member (5')
# - [ ] 3 · The fact table, and a grain test (6')
# - [ ] 4 · Five finance questions against the key (8')
# - [ ] ✱ Stretch · Allocate freight by pieces instead of revenue: which answers move?

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
import pandas as pd

STAGING = ["stg_orders", "stg_order_lines", "stg_products", "stg_customers", "stg_prices", "stg_shipments"]
con = Q.warehouse()
print("built:", Q.build_models(con, names=STAGING))
FA = Q.reference("finance_answers")

# %% [markdown]
# ## 1 · Draw the star: grain, facts, dimensions (6')
#
# Grain first: what is one row of the fact table? Every question must be answerable by summing facts at that
# grain and grouping by dimension attributes.
#
# ✏️ **Exercise** · Fill `STAR`: the grain in one sentence, the additive facts, and for each dimension its key and
# the attributes the five questions need. Draw it on paper too.

# %%
# BEGIN SOLUTION
STAR = {
    "grain": "one row per line of a confirmed order",
    "facts": ["qty_pieces", "revenue", "cost", "freight"],
    "dimensions": {
        "dim_date": ("order_date", ["month"]),
        "dim_customer": ("customer_id", ["customer_type", "city"]),
        "dim_product": ("product_id", ["category"]),
        "dim_supplier": ("supplier_key", ["country"]),       # type 2: the version valid when the order was created
    },
}
# END SOLUTION

# %%
try:
    STAR
except NameError:
    STAR = {"grain": "one row per line of a confirmed order", "facts": ["qty_pieces", "revenue", "cost", "freight"],
            "dimensions": {"dim_date": ("order_date", ["month"]), "dim_customer": ("customer_id", ["customer_type", "city"]),
                           "dim_product": ("product_id", ["category"]), "dim_supplier": ("supplier_key", ["country"])}}
needed = {"month", "customer_type", "city", "category", "country"}
have = {a for _, attrs in STAR["dimensions"].values() for a in attrs}
Q.check("line" in STAR["grain"], "the grain names the order line")
Q.check(needed <= have and "freight" in STAR["facts"], "every attribute and fact the five questions need is in the star")

# %% [markdown]
# ## 2 · Dimensions with an unknown member (5')
#
# Customer C-1187 asked to be erased: the customer row is gone, 13 orders remain. An inner join to the customer
# dimension would drop their revenue. A dimension gets an **unknown member**, and the fact points to it.
#
# ✏️ **Exercise** · Create `mart.dim_customer` from `stg.customers` plus one row `('Unknown', 'Unknown customer',
# 'Unknown', 'Unknown')`, and `mart.dim_product` from `stg.products`. The supplier dimension is given: Lab 2.3's
# type 2 table with a key per version.

# %%
con.execute("CREATE SCHEMA IF NOT EXISTS mart")
# BEGIN SOLUTION
con.execute("""CREATE OR REPLACE TABLE mart.dim_customer AS
    SELECT customer_id, name, customer_type, city FROM stg.customers
    UNION ALL SELECT 'Unknown', 'Unknown customer', 'Unknown', 'Unknown'""")
con.execute("CREATE OR REPLACE TABLE mart.dim_product AS SELECT product_id, name, category, units_per_carton FROM stg.products")
# END SOLUTION

# %%
try:
    con.execute("SELECT 1 FROM mart.dim_customer LIMIT 1").fetchall()
except Exception:  # noqa: BLE001 - safety net
    Q.build_models(con, names=["dim_customer", "dim_product"])
Q.build_models(con, names=["dim_supplier"])
print(con.sql("SELECT supplier_key, supplier_id, country, valid_from, valid_to FROM mart.dim_supplier WHERE supplier_id = 'S-07'"))
Q.check(con.execute("SELECT count(*) FROM mart.dim_customer WHERE customer_id = 'Unknown'").fetchall()[0][0] == 1, "one unknown member")

# %% [markdown]
# ## 3 · The fact table, and a grain test (6')
#
# Freight is charged **per shipment** (one per order), not per line. Join it to the lines and every line of an
# order carries the whole freight: the classic fan-out. First see it, then fix it by sharing each shipment's
# freight among its lines in proportion to revenue.

# %%
fan = con.execute("""
    SELECT (SELECT round(sum(freight_sar)) FROM stg.shipments) AS freight_billed,
           round(sum(s.freight_sar)) AS freight_after_naive_join
    FROM stg.order_lines l JOIN stg.orders o ON o.order_id = l.order_id AND o.status = 'confirmed'
    JOIN stg.shipments s ON s.order_id = l.order_id""").fetchall()[0]
print(f"freight billed {fan[0]:,.0f} SAR | after joining it to lines {fan[1]:,.0f} SAR ({fan[1] / fan[0]:.1f} times)")

# %% [markdown]
# ✏️ **Exercise** · Create `mart.fct_order_line` at the grain you stated: confirmed orders only, the customer or
# `'Unknown'`, `qty_pieces`, `revenue`, `cost` (pieces times the price valid on the order date), `freight` (the
# shipment's freight times the line's share of the order's revenue) and `supplier_key` (the supplier version valid
# when the order was **created**). Then write the grain test: no `(order_id, line_no)` twice.

# %%
# BEGIN SOLUTION
con.execute("""CREATE OR REPLACE TABLE mart.fct_order_line AS
WITH lines AS (
  SELECT l.order_id, l.line_no, o.order_date, o.created_at, coalesce(c.customer_id, 'Unknown') AS customer_id,
         l.product_id, p.supplier_id,
         l.qty * CASE WHEN l.unit = 'carton' THEN p.units_per_carton ELSE 1 END AS qty_pieces,
         l.qty * l.unit_price_sar * (1 - l.discount_pct / 100) AS revenue
  FROM stg.order_lines l
  JOIN stg.orders o ON o.order_id = l.order_id AND o.status = 'confirmed'
  JOIN stg.products p ON p.product_id = l.product_id
  LEFT JOIN stg.customers c ON c.customer_id = o.customer_id)
SELECT lines.order_id, lines.line_no, lines.order_date, lines.customer_id, lines.product_id, s.supplier_key,
       lines.qty_pieces,
       CAST(lines.revenue AS DECIMAL(14, 2)) AS revenue,
       CAST(lines.qty_pieces * pr.cost_piece_sar AS DECIMAL(14, 2)) AS cost,
       CAST(sh.freight_sar * lines.revenue / sum(lines.revenue) OVER (PARTITION BY lines.order_id) AS DECIMAL(14, 4)) AS freight
FROM lines
JOIN stg.prices pr ON pr.product_id = lines.product_id AND lines.order_date BETWEEN pr.valid_from AND pr.valid_to
LEFT JOIN stg.shipments sh ON sh.order_id = lines.order_id
LEFT JOIN mart.dim_supplier s ON s.supplier_id = lines.supplier_id
     AND lines.created_at >= s.valid_from AND lines.created_at < s.valid_to""")
grain_dupes = con.execute("SELECT count(*) FROM (SELECT order_id, line_no FROM mart.fct_order_line GROUP BY ALL HAVING count(*) > 1)").fetchall()[0][0]
# END SOLUTION

# %%
try:
    grain_dupes
except NameError:  # safety net
    Q.build_models(con, names=["fct_order_line"])
    grain_dupes = con.execute("SELECT count(*) FROM (SELECT order_id, line_no FROM mart.fct_order_line GROUP BY ALL HAVING count(*) > 1)").fetchall()[0][0]
rows, freight = con.execute("SELECT count(*), round(sum(freight)) FROM mart.fct_order_line").fetchall()[0]
orphans = con.execute("SELECT count(*) FROM mart.fct_order_line f LEFT JOIN mart.dim_customer c USING (customer_id) WHERE c.customer_id IS NULL").fetchall()[0][0]
print(f"{rows:,} fact rows | freight {freight:,.0f} SAR | duplicate keys {grain_dupes} | lines without a customer row {orphans}")
Q.check(grain_dupes == 0 and rows == 17665, "the grain holds: 17,665 lines of confirmed orders, each once")
Q.check(abs(freight - fan[0]) < 2, "freight is counted once")
Q.check(orphans == 0, "every line finds a customer, the unknown member included")

# %% [markdown]
# ## 4 · Five finance questions against the key (8')
#
# ✏️ **Exercise** · Write the five queries in `QUESTIONS` against the star only (the fact joined to dimensions,
# never to staging). Each returns the grouping columns, then `revenue`, `cost` and `margin`, rounded to 2 decimals;
# question 5 adds `freight` and `margin_after_freight`.

# %%
BASE = """FROM mart.fct_order_line f JOIN mart.dim_customer c USING (customer_id) JOIN mart.dim_product p USING (product_id)
          LEFT JOIN mart.dim_supplier s USING (supplier_key)"""
M = "round(sum(revenue), 2) AS revenue, round(sum(cost), 2) AS cost, round(sum(revenue) - sum(cost), 2) AS margin"
# BEGIN SOLUTION
QUESTIONS = {
    "q1_monthly": f"SELECT strftime(order_date, '%Y-%m') AS month, {M} {BASE} GROUP BY 1 ORDER BY 1",
    "q2_type_city": f"SELECT customer_type, city, {M} {BASE} GROUP BY 1, 2 ORDER BY 1, 2",
    "q3_country_at_order": f"SELECT coalesce(s.country, 'Unknown') AS country, {M} {BASE} GROUP BY 1 ORDER BY 1",
    "q4_category_month": f"SELECT category, strftime(order_date, '%Y-%m') AS month, {M} {BASE} GROUP BY 1, 2 ORDER BY 1, 2",
    "q5_city_after_freight": f"""SELECT city, {M}, round(sum(freight), 2) AS freight,
                                 round(sum(revenue) - sum(cost) - sum(freight), 2) AS margin_after_freight {BASE} GROUP BY 1 ORDER BY 1""",
}
# END SOLUTION

# %%
try:
    QUESTIONS
except NameError:  # safety net: the answers themselves
    QUESTIONS = None
results = {}
for q, rows in FA.items():
    mine = con.sql(QUESTIONS[q]).df() if QUESTIONS else pd.DataFrame(rows)
    ref = pd.DataFrame(rows)
    keys = [c for c in ref.columns if c not in ("revenue", "cost", "margin", "margin_pct", "freight", "margin_after_freight")]
    m = ref.merge(mine, on=keys, suffixes=("_ref", ""), how="outer")
    worst = max((m[f"{v}_ref"] - m[v].astype(float)).abs().max() for v in ("revenue", "cost", "margin"))
    results[q] = {"groups": len(ref), "matched": int(m["revenue"].notna().sum()), "largest difference (SAR)": round(float(worst), 2)}
res = pd.DataFrame(results).T
print(res)
Q.check(all(r["matched"] == r["groups"] and r["largest difference (SAR)"] < 5 for r in results.values()),
        "all five questions match finance's key (within a few riyals of rounding)")
print(con.sql(QUESTIONS["q5_city_after_freight"]) if QUESTIONS else "")

# %% [markdown]
# 🔍 Question 5: which city has the highest margin before freight, and which after? Riyadh and Dammam pay more
# freight per order than Jeddah (the warehouse is in Jeddah).

# %% [markdown]
# ## ✱ Stretch · Allocate freight by pieces
#
# Revenue share is one allocation rule; pieces (a stand-in for weight) is another. Re-allocate and compare the
# freight by city (question 5) and by category. Which answer moves, why does the other not, and who in finance must
# agree on the rule?

# %%
# BEGIN SOLUTION
print(con.sql("""
    WITH f AS (
      SELECT f.*, sh.freight_sar * f.qty_pieces / sum(f.qty_pieces) OVER (PARTITION BY f.order_id) AS freight_by_pieces
      FROM mart.fct_order_line f LEFT JOIN stg.shipments sh USING (order_id))
    SELECT c.city, round(sum(freight)) AS by_revenue, round(sum(freight_by_pieces)) AS by_pieces
    FROM f JOIN mart.dim_customer c USING (customer_id) GROUP BY 1 ORDER BY 1"""))
print(con.sql("""
    WITH f AS (
      SELECT f.*, sh.freight_sar * f.qty_pieces / sum(f.qty_pieces) OVER (PARTITION BY f.order_id) AS freight_by_pieces
      FROM mart.fct_order_line f LEFT JOIN stg.shipments sh USING (order_id))
    SELECT p.category, round(sum(freight)) AS by_revenue, round(sum(freight_by_pieces)) AS by_pieces
    FROM f JOIN mart.dim_product p USING (product_id) GROUP BY 1 ORDER BY 1"""))
print("City totals cannot move: all lines of an order share one city. Category totals move: an order mixes categories.")
# END SOLUTION

# %% [markdown]
# ## Checkpoint
#
# 1. Freight is per shipment. What happens when you join it to lines, and what are the two fixes?
#    <details><summary>Answer</summary>Each line repeats the shipment's freight, so the sum multiplies it. Either
#    allocate it to lines by a stated rule (as here), or keep a second fact table at shipment grain.</details>
# 2. Why does the fact table carry `supplier_key` rather than `supplier_id`?
#    <details><summary>Answer</summary>The key points to the supplier version valid when the order was created, so
#    S-07's August orders stay "AE" after it moved to Saudi Arabia.</details>
# 3. Why an unknown member rather than a LEFT JOIN in every report?
#    <details><summary>Answer</summary>Every report then gets the same answer with an inner join, and the unknown
#    revenue is visible as its own row instead of vanishing in some reports and not others.</details>
#
# **Carry forward.** These tables are the reference models in `labs/models/`, which Lab 3.2 puts under version control.
