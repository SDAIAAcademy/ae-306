# %% [markdown]
# # Lab 3.3 · A contract that holds
#
# Day 3 · Session 3 (Data quality tests and contracts) · 25 min. On 1 November the supplier feed's producer renamed
# `cost` to `unit_cost` and sent one negative cost, without telling anyone. In this lab you write tests on the staged
# prices, read the data contract for the feed (Open Data Contract Standard), compile its rules to SQL checks, and
# break the feed on purpose: the gate must keep the price table that the margin reads unchanged.
#
# **AI-tutor.** An AI assistant may give hints in this lab; it does not write your queries, models or tests.
#
# **Reference state.** `data/raw/supplier_api/price_records.jsonl` (the feed to 31 October),
# `batch_2026-11-01.jsonl` (the broken November batch), `batch_2026-11-01_fixed.jsonl` (the producer's fix) and
# `contracts/supplier_prices.odcs.yaml`. Nothing from another lab is needed.
#
# **Tasks**
# - [ ] 1 · Tests on the staged prices (6')
# - [ ] 2 · The contract in YAML (6')
# - [ ] 3 · Compile the contract to SQL checks (6')
# - [ ] 4 · Break the feed: the gate holds (7')
# - [ ] ✱ Stretch · Quarantine the failing rows instead of blocking: when is that right?

# %%
import os, sys, subprocess
from pathlib import Path

IN_COLAB = "google.colab" in sys.modules
if IN_COLAB:
    REPO_URL = "https://github.com/SDAIAAcademy/ae-306.git"
    if not Path("/content/data-engineering").exists():
        subprocess.run(["git", "clone", "-q", REPO_URL, "/content/data-engineering"], check=True)
    os.chdir("/content/data-engineering/labs")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements-colab.txt"], check=True)
else:
    while not Path("qafila.py").exists() and Path.cwd() != Path.cwd().parent:
        os.chdir("..")  # solutions/ notebooks run from labs/
sys.path.insert(0, os.getcwd())

import qafila as Q
import contract_gate as G
import pandas as pd

API = Q.posix(Q.RAW / "supplier_api")
con = Q.connect()
con.execute(G.NUM_MACRO)
con.execute(f"CREATE TABLE products AS SELECT * FROM read_csv('{Q.posix(Q.EXTRACTS)}/products.csv')")
con.execute(f"CREATE TABLE feed AS SELECT * FROM read_json('{API}/price_records.jsonl', format = 'newline_delimited')")
con.execute("""CREATE TABLE stg_prices AS
    SELECT price_id, product_id, num(cost) AS cost, currency, unit, valid_from, updated_at FROM feed
    QUALIFY row_number() OVER (PARTITION BY price_id ORDER BY updated_at DESC) = 1""")
print(con.sql("SELECT * FROM stg_prices LIMIT 3"))

# %% [markdown]
# ## 1 · Tests on the staged prices (6')
#
# A test is a query that returns the rows breaking a rule; zero rows is a pass. Four kinds cover most of a
# staging table: **not null**, **unique**, **accepted values** and **relationships** (every key exists in its parent).
#
# ✏️ **Exercise** · Fill `TESTS` with one query of each kind on `stg_prices`, plus `cost_positive`.

# %%
# BEGIN SOLUTION
TESTS = {
    "price_id_not_null": "SELECT * FROM stg_prices WHERE price_id IS NULL",
    "price_id_unique": "SELECT price_id FROM stg_prices GROUP BY 1 HAVING count(*) > 1",
    "currency_accepted": "SELECT * FROM stg_prices WHERE currency NOT IN ('SAR', 'USD', 'AED')",
    "product_exists": "SELECT * FROM stg_prices WHERE product_id NOT IN (SELECT product_id FROM products)",
    "cost_positive": "SELECT * FROM stg_prices WHERE cost IS NULL OR cost <= 0",
}
# END SOLUTION

# %%
try:
    TESTS
except NameError:  # safety net
    TESTS = {"price_id_unique": "SELECT price_id FROM stg_prices GROUP BY 1 HAVING count(*) > 1",
             "cost_positive": "SELECT * FROM stg_prices WHERE cost IS NULL OR cost <= 0"}


def run_tests(tests: dict) -> pd.DataFrame:
    return pd.DataFrame([{"test": k, "failing_rows": con.execute(f"SELECT count(*) FROM ({q})").fetchall()[0][0]} for k, q in tests.items()])


t = run_tests(TESTS)
print(t.to_string(index=False))
Q.check(len(t) >= 5 and (t.failing_rows == 0).all(), "every test passes on the October feed")
con.execute("CREATE TABLE bad AS SELECT * FROM stg_prices")
con.execute("INSERT INTO bad SELECT * REPLACE (-cost AS cost) FROM stg_prices LIMIT 1")
bad = pd.DataFrame([{"test": k, "failing_rows": con.execute(f"SELECT count(*) FROM ({q.replace('stg_prices', 'bad')})").fetchall()[0][0]}
                    for k, q in TESTS.items()])
print(bad.to_string(index=False))
Q.check(bad.failing_rows.sum() >= 2, "one bad row trips both the unique and the positive-cost test")

# %% [markdown]
# ## 2 · The contract in YAML (6')
#
# Tests belong to the consumer. A **data contract** is agreed with the producer: the columns, their types, which are
# required, and quality rules, in a standard format (ODCS) that tools on both sides read.

# %%
contract = G.load(Path("contracts/supplier_prices.odcs.yaml"))
props = contract["schema"][0]["properties"]
print("apiVersion:", contract["apiVersion"], "| owner:", contract["team"][0]["username"])
print(pd.DataFrame([{"property": p["name"], "type": p["logicalType"], "required": p.get("required", False),
                     "rules": ", ".join(r["id"] for r in p.get("quality", []))} for p in props]).to_string(index=False))

# %% [markdown]
# ✏️ **Exercise** · Read the contract and answer in the cell below: which rule would catch a negative cost? Which
# would catch the column renamed to `unit_cost`? Is `incoterm` required, and why is that right?

# %% [markdown]
# *Your answer here.*

# %% [markdown]
# ## 3 · Compile the contract to SQL checks (6')
#
# ✏️ **Exercise** · Write `my_rule_sql(rule, table, prop)`: the SQL that returns one number for a quality rule, for
# the metrics `nullValues`, `duplicateValues` (with `arguments.properties`), `invalidValues` (with
# `arguments.validValues`), `rowCount`, and `type: sql` (replace `{object}` and `{property}`). Then compare yours
# with the course's compiler, `G.rule_sql`, on every rule of the contract.

# %%
def my_rule_sql(rule: dict, table: str, prop: str | None) -> str:
    # BEGIN SOLUTION
    if rule.get("type") == "sql":
        return rule["query"].replace("{object}", table).replace("{property}", prop or "")
    a = rule.get("arguments", {})
    if rule["metric"] == "rowCount":
        return f"SELECT count(*) FROM {table}"
    if rule["metric"] == "nullValues":
        return f"SELECT count(*) FROM {table} WHERE {prop} IS NULL"
    if rule["metric"] == "duplicateValues":
        return f"SELECT count(*) - count(DISTINCT ({', '.join(a.get('properties', [prop]))})) FROM {table}"
    if rule["metric"] == "invalidValues":
        values = ", ".join(f"'{v}'" for v in a["validValues"])
        return f"SELECT count(*) FROM {table} WHERE {prop} IS NULL OR {prop} NOT IN ({values})"
    raise ValueError(rule["metric"])
    # END SOLUTION


# %%
rules = [(r, None) for r in contract["schema"][0].get("quality", [])] + [(r, p["name"]) for p in props for r in p.get("quality", [])]
same = 0
for rule, prop in rules:
    try:
        mine = con.execute(my_rule_sql(rule, "feed", prop)).fetchall()[0][0]
    except NotImplementedError:
        mine = con.execute(G.rule_sql(rule, "feed", prop)).fetchall()[0][0]
    ref = con.execute(G.rule_sql(rule, "feed", prop)).fetchall()[0][0]
    same += mine == ref
    print(f"{rule['id']:24s} {G.rule_sql(rule, 'feed', prop)[:80]:82s} -> {ref}")
Q.check(same == len(rules), f"your compiler and the course's agree on all {len(rules)} rules")

# %% [markdown]
# ## 4 · Break the feed: the gate holds (7')
#
# The pipeline: land the batch in `incoming`, run the contract against it, and only if every check passes merge it
# into `current_prices`, the table the margin reads. A failed gate leaves `current_prices` exactly as it was.
#
# ✏️ **Exercise** · Write `refresh(batch_file)`: load the batch into `incoming`, run `G.run(con, contract,
# "incoming")`, and when every check passed insert the new versions into `current_prices` (latest per
# `price_id`). Return the list of failed check ids (empty when the refresh happened).

# %%
con.execute("CREATE OR REPLACE TABLE current_prices AS SELECT price_id, product_id, num(cost) AS cost, currency, unit, valid_from, updated_at FROM stg_prices")


def fingerprint() -> tuple:
    return con.execute("SELECT count(*), round(sum(cost), 2), max(updated_at) FROM current_prices").fetchall()[0]


def refresh(batch_file: str) -> list[str]:
    # BEGIN SOLUTION
    con.execute(f"CREATE OR REPLACE TABLE incoming AS SELECT * FROM read_json('{API}/{batch_file}', format = 'newline_delimited')")
    failed = [r["id"] for r in G.run(con, contract, "incoming") if not r["passed"]]
    if failed:
        return failed
    con.execute("""DELETE FROM current_prices WHERE price_id IN (SELECT price_id FROM incoming)""")
    con.execute("""INSERT INTO current_prices
                   SELECT price_id, product_id, num(cost), currency, unit, valid_from, updated_at FROM incoming""")
    return []
    # END SOLUTION


# %%
before = fingerprint()
try:
    failed = refresh("batch_2026-11-01.jsonl")
except NotImplementedError:  # safety net: the broken batch, as the solution reports it
    con.execute(f"CREATE OR REPLACE TABLE incoming AS SELECT * FROM read_json('{API}/batch_2026-11-01.jsonl', format = 'newline_delimited')")
    failed = [r["id"] for r in G.run(con, contract, "incoming") if not r["passed"]]
print("broken batch, failed checks:", failed)
print(pd.DataFrame(G.run(con, contract, "incoming"))[["id", "value", "passed", "error"]].to_string(index=False))
Q.check(bool(failed) and "cost_present" in failed, "the renamed column fails the gate")
Q.check(fingerprint() == before, "current_prices is unchanged: the margin still reads October's prices")

# %%
try:
    failed_fixed = refresh("batch_2026-11-01_fixed.jsonl")
except NotImplementedError:
    failed_fixed = []
print("fixed batch, failed checks:", failed_fixed, "| current_prices", before, "->", fingerprint())
Q.check(not failed_fixed, "the producer's fix passes the contract")

# %% [markdown]
# 🔍 The broken batch also carries a negative cost. With the column renamed, the cost rule cannot even run: one
# contract failure can hide another. Find the negative value in `incoming.unit_cost`.

# %%
con.execute(f"CREATE OR REPLACE TABLE incoming AS SELECT * FROM read_json('{API}/batch_2026-11-01.jsonl', format = 'newline_delimited')")
print(con.sql("SELECT price_id, unit_cost, num(unit_cost) AS value FROM incoming WHERE num(unit_cost) <= 0"))

# %% [markdown]
# ## ✱ Stretch · Quarantine instead of blocking
#
# Blocking stops everything for one bad row. Quarantine loads the good rows and parks the bad ones with the
# reason. Apply it to the broken batch with the column mapped back: which rows load, which wait, and why is
# quarantine wrong for the renamed column itself?

# %%
# BEGIN SOLUTION
con.execute("CREATE OR REPLACE TABLE mapped AS SELECT * EXCLUDE (unit_cost), unit_cost AS cost FROM incoming")
con.execute("CREATE OR REPLACE TABLE quarantine AS SELECT *, 'cost not a positive number' AS reason FROM mapped WHERE num(cost) IS NULL OR num(cost) <= 0")
con.execute("CREATE OR REPLACE TABLE loadable AS SELECT * FROM mapped WHERE NOT (num(cost) IS NULL OR num(cost) <= 0)")
print(con.sql("SELECT (SELECT count(*) FROM loadable) AS loadable, (SELECT count(*) FROM quarantine) AS quarantined"))
print("A renamed column is not a bad row: every row is affected, so the batch blocks until the producer fixes it.")
# END SOLUTION

# %% [markdown]
# ## Checkpoint
#
# 1. The contract fails on a renamed column in the night run. What should the pipeline do?
#    <details><summary>Answer</summary>Block the refresh of everything downstream, keep the batch in raw, alert the
#    owner named in the contract, and refresh after the fix. The mart keeps yesterday's numbers.</details>
# 2. A test and a contract: what is the difference?
#    <details><summary>Answer</summary>A test is the consumer's check on its own tables. A contract is an agreement
#    with the producer, versioned and readable by both sides, so a breaking change is a breach that someone owns.</details>
# 3. When is quarantine better than blocking?
#    <details><summary>Answer</summary>When the failures are a few rows and the rest are independent of them (one
#    negative cost). Not when the whole batch is affected (a renamed column) or when a missing row changes a total
#    finance reports.</details>
#
# **Carry forward.** `contract_gate.py` and the contract become the blocking check of Lab 3.4.
