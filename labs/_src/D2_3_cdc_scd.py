# %% [markdown]
# # Lab 2.3 · Supplier changes and their history
#
# Day 2 · Session 3 (Change data capture, merge and history) · 25 min. Procurement's supplier table changes:
# payment terms, contacts, one supplier moves country, one is deleted, two are added. A log-based change feed
# (Debezium-style events) carries each change. In this lab you apply the feed to a copy with `MERGE`, reconcile the
# copy with the source, and keep supplier history as a type 2 slowly changing dimension with validity ranges.
#
# **AI-tutor.** An AI assistant may give hints in this lab; it does not write your queries, models or tests.
#
# **Reference state.** `data/raw/suppliers/suppliers_2026-08-01.csv` (the snapshot the feed starts from),
# `supplier_changes.jsonl` (the feed), `suppliers_2026-10-31.csv` (the source table at the end, for the
# reconciliation). Nothing from another lab is needed.
#
# **Tasks**
# - [ ] 1 · Read the feed: duplicates and out-of-order events (5')
# - [ ] 2 · Latest state per supplier with MERGE (7')
# - [ ] 3 · Reconcile with the source snapshot (4')
# - [ ] 4 · Type 2 history with valid ranges (9')
# - [ ] ✱ Stretch · As-of join: margin by supplier country at order time

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

S = Q.posix(Q.RAW / "suppliers")
con = Q.connect()
con.execute(f"CREATE TABLE snapshot AS SELECT * FROM read_csv('{S}/suppliers_2026-08-01.csv')")
con.execute(f"""CREATE TABLE feed AS
    SELECT row_number() OVER () AS arrival, op, before, after,
           source.lsn AS lsn, make_timestamptz(source.ts_ms * 1000) AS changed_at
    FROM read_json('{S}/supplier_changes.jsonl', format = 'newline_delimited')""")
print(con.sql("SELECT arrival, op, lsn, changed_at, coalesce(after.supplier_id, before.supplier_id) AS supplier FROM feed LIMIT 6"))

# %% [markdown]
# ## 1 · Read the feed: duplicates and out-of-order events (5')
#
# Each event has an envelope: `op` (`c` create, `u` update, `d` delete), the row `before` and `after`, and the
# source's **log position** (`lsn`), which orders changes as the database committed them. Arrival order is the
# order the events reached you.
#
# ✏️ **Exercise** · Count the events delivered twice (same `lsn`) as `dupes`, and the events that arrived after an
# event with a higher `lsn` for the same supplier as `late`.

# %%
# BEGIN SOLUTION
dupes = con.execute("SELECT count(*) - count(DISTINCT lsn) FROM feed").fetchall()[0][0]
late = con.execute("""
    WITH f AS (SELECT DISTINCT ON (lsn) * FROM feed ORDER BY lsn, arrival)
    SELECT count(*) FROM (
      SELECT lsn < max(lsn) OVER (PARTITION BY coalesce(after.supplier_id, before.supplier_id) ORDER BY arrival
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS is_late
      FROM f) WHERE is_late""").fetchall()[0][0]
# END SOLUTION

# %%
try:
    dupes, late
except NameError:  # safety net
    dupes, late = 3, 1
print(f"{dupes} duplicate deliveries, {late} event(s) arrived after a newer change to the same supplier")
Q.check(dupes == 3 and late == 1, "three duplicates and one late event")

# %% [markdown]
# ## 2 · Latest state per supplier with MERGE (7')
#
# ✏️ **Exercise** · Build `latest`: one row per supplier, the change with the highest `lsn` (duplicates gone),
# with `op` and the `after` fields as columns. Then `MERGE INTO suppliers` (a copy of the snapshot): delete on
# `d`, update when matched, insert when not matched.

# %%
con.execute("CREATE OR REPLACE TABLE suppliers AS SELECT * FROM snapshot")
COLS = ["supplier_id", "name_en", "name_ar", "country", "currency", "payment_terms_days", "contact_name",
        "contact_email", "iban", "contract_ref"]
# BEGIN SOLUTION
con.execute("""CREATE OR REPLACE TABLE latest AS
    SELECT op, coalesce(after.supplier_id, before.supplier_id) AS sid, after.*
    FROM feed
    QUALIFY row_number() OVER (PARTITION BY coalesce(after.supplier_id, before.supplier_id) ORDER BY lsn DESC) = 1""")
con.execute(f"""
    MERGE INTO suppliers AS t USING latest AS s ON t.supplier_id = s.sid
    WHEN MATCHED AND s.op = 'd' THEN DELETE
    WHEN MATCHED THEN UPDATE SET {', '.join(f'{c} = s.{c}' for c in COLS[1:])}
    WHEN NOT MATCHED AND s.op <> 'd' THEN INSERT ({', '.join(COLS)}) VALUES ({', '.join('s.' + c for c in COLS)})""")
# END SOLUTION

# %%
n_sup = con.execute("SELECT count(*) FROM suppliers").fetchall()[0][0]
if n_sup == 18 and not con.execute("SELECT count(*) FROM suppliers WHERE supplier_id = 'S-19'").fetchall()[0][0]:
    con.execute(f"CREATE OR REPLACE TABLE suppliers AS SELECT * FROM read_csv('{S}/suppliers_2026-10-31.csv')")  # safety net
    n_sup = 19
print(con.sql("SELECT supplier_id, name_en, country, currency, payment_terms_days FROM suppliers ORDER BY 1"))
Q.check(n_sup == 19, "18 suppliers, one deleted (S-12), two created (S-19, S-20): 19")

# %% [markdown]
# ## 3 · Reconcile with the source snapshot (4')
#
# The source table at the end of October is the truth. A copy that reconciles has no row in either direction of
# `EXCEPT`. Then see what arrival order would have given.

# %%
truth = f"read_csv('{S}/suppliers_2026-10-31.csv')"
only_copy = con.execute(f"SELECT count(*) FROM (SELECT * FROM suppliers EXCEPT SELECT * FROM {truth})").fetchall()[0][0]
only_source = con.execute(f"SELECT count(*) FROM (SELECT * FROM {truth} EXCEPT SELECT * FROM suppliers)").fetchall()[0][0]
print("rows only in the copy:", only_copy, "| rows only in the source:", only_source)
Q.check(only_copy == 0 and only_source == 0, "the copy reconciles with the source")

print(con.sql("""SELECT arrival, lsn, changed_at, after.payment_terms_days AS terms, after.contact_email AS email
                 FROM feed WHERE after.supplier_id = 'S-15' ORDER BY arrival"""))

# %% [markdown]
# 🔍 Read S-15's events in arrival order. Event 12 is older (lower `lsn`) than event 11. A copy that applied events
# as they arrived would have put the old e-mail address back after event 12 and kept it wrong until event 13: no
# error, just a wrong supplier contact until event 13 happened to arrive. Ordering by `lsn` never goes backwards.

# %% [markdown]
# ## 4 · Type 2 history with valid ranges (9')
#
# A type 2 dimension keeps one row per **version** of a supplier: `valid_from` inclusive, `valid_to` exclusive
# (empty for the current version). The first version of each snapshot supplier starts on 2026-08-01; each change
# starts a new version at its `changed_at` and ends the one before; a delete ends the last version and starts
# none.
#
# ✏️ **Exercise** · Build `dim_supplier` with the columns of the snapshot plus `valid_from` and `valid_to`.

# %%
# BEGIN SOLUTION
con.execute(f"""CREATE OR REPLACE TABLE dim_supplier AS
WITH versions AS (
  SELECT {', '.join(COLS)}, TIMESTAMPTZ '2026-08-01 00:00:00+03' AS valid_from, 0 AS lsn, false AS is_delete FROM snapshot
  UNION ALL
  SELECT DISTINCT ON (lsn) {', '.join('after.' + c for c in COLS)}, changed_at, lsn, false
  FROM feed WHERE op IN ('c', 'u')
  UNION ALL
  SELECT DISTINCT ON (lsn) before.supplier_id, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, changed_at, lsn, true
  FROM feed WHERE op = 'd'),
ranged AS (
  SELECT *, lead(valid_from) OVER (PARTITION BY supplier_id ORDER BY lsn) AS valid_to FROM versions)
SELECT {', '.join(COLS)}, valid_from, valid_to FROM ranged WHERE NOT is_delete ORDER BY supplier_id, valid_from""")
# END SOLUTION

# %%
ref = f"read_csv('{Q.posix(Q.REF)}/dim_supplier.csv', types = {{'valid_from': 'TIMESTAMPTZ', 'valid_to': 'TIMESTAMPTZ'}})"
try:
    rows = con.execute("SELECT count(*) FROM dim_supplier").fetchall()[0][0]
except Exception:  # noqa: BLE001 - safety net
    con.execute(f"CREATE OR REPLACE TABLE dim_supplier AS SELECT * FROM {ref}")
    rows = con.execute("SELECT count(*) FROM dim_supplier").fetchall()[0][0]
diff = con.execute(f"""SELECT count(*) FROM (
    (SELECT supplier_id, country, payment_terms_days, contact_email, valid_from, valid_to FROM dim_supplier
     EXCEPT SELECT supplier_id, country, payment_terms_days, contact_email, valid_from, valid_to FROM {ref})
    UNION ALL
    (SELECT supplier_id, country, payment_terms_days, contact_email, valid_from, valid_to FROM {ref}
     EXCEPT SELECT supplier_id, country, payment_terms_days, contact_email, valid_from, valid_to FROM dim_supplier))""").fetchall()[0][0]
print(con.sql("SELECT supplier_id, name_en, country, valid_from, valid_to FROM dim_supplier WHERE supplier_id IN ('S-07', 'S-12', 'S-19')"))
overlaps = con.execute("""SELECT count(*) FROM dim_supplier a JOIN dim_supplier b USING (supplier_id)
    WHERE a.valid_from < b.valid_from AND coalesce(a.valid_to, TIMESTAMPTZ '9999-12-31 00:00:00+00') > b.valid_from""").fetchall()[0][0]
current = con.execute("SELECT count(*) FROM dim_supplier WHERE valid_to IS NULL").fetchall()[0][0]
print(f"{rows} versions | {current} current | overlapping ranges: {overlaps} | differences from the reference: {diff}")
Q.check(rows == 52 and current == 19 and overlaps == 0 and diff == 0, "52 versions, 19 current, no overlap, equal to the reference")

# %% [markdown]
# ## ✱ Stretch · Margin by supplier country at order time
#
# S-07 moved from the UAE to Saudi Arabia on 1 September. An order of August belongs to "AE", one of
# October to "SA". Join each confirmed line to the supplier version valid when the order was created.

# %%
# BEGIN SOLUTION
wh = Q.warehouse()
Q.build_models(wh, names=["stg_orders", "stg_order_lines", "stg_products", "stg_prices"])
wh.register("hist", con.sql("SELECT * FROM dim_supplier").df())
by_country = wh.sql("""
    SELECT coalesce(h.country, 'Unknown') AS country,
           round(sum(l.qty * l.unit_price_sar * (1 - l.discount_pct / 100)), 2) AS revenue
    FROM stg.order_lines l JOIN stg.orders o ON o.order_id = l.order_id AND o.status = 'confirmed'
    JOIN stg.products p USING (product_id)
    LEFT JOIN hist h ON h.supplier_id = p.supplier_id AND o.created_at >= h.valid_from
                    AND o.created_at < coalesce(h.valid_to, TIMESTAMPTZ '9999-12-31 00:00:00+00')
    GROUP BY 1 ORDER BY 1""").df()
print(by_country.to_string(index=False))
q3 = {r["country"]: r["revenue"] for r in Q.reference("finance_answers")["q3_country_at_order"]}
Q.check(all(abs(q3[c] - v) < 5 for c, v in zip(by_country.country, by_country.revenue)), "equals finance's question 3")
# END SOLUTION

# %% [markdown]
# ## Checkpoint
#
# 1. Two events for one supplier arrive out of order. What decides which one wins?
#    <details><summary>Answer</summary>The source's log position (<code>lsn</code>), never arrival time: it is the
#    order in which the database committed the changes.</details>
# 2. Why do the validity ranges use an exclusive `valid_to`?
#    <details><summary>Answer</summary>So that consecutive versions meet without a gap or an overlap: a moment
#    belongs to exactly one version with <code>valid_from &lt;= t &lt; valid_to</code>.</details>
# 3. The source deletes a supplier. What happens to its rows in the type 2 dimension?
#    <details><summary>Answer</summary>Its last version gets a <code>valid_to</code>; no row is removed. Old orders
#    still join to the version that was valid when they were placed.</details>
#
# **Carry forward.** `data/reference/dim_supplier.csv` is this table; Day 3's `mart.dim_supplier` reads it.
