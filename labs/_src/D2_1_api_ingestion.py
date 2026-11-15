# %% [markdown]
# # Lab 2.1 · An incremental, idempotent API load
#
# Day 2 · Session 1 (Ingesting from APIs) · 25 min. Ammar Basri's suppliers publish their prices through an API:
# pages of 20 records, a cursor to the next page, a `429 Too Many Requests` every few calls, and corrections re-sent
# later with a new `updated_at`. In this lab you load it into DuckDB with plain Python, store the load state with
# the data, and show that running the load twice adds nothing.
#
# **AI-tutor.** An AI assistant may give hints in this lab; it does not write your queries, models or tests.
#
# **Reference state.** `Q.SupplierAPI(release=1)` serves the API in this notebook (on 127.0.0.1) as it stood on
# 15 October; `release=2` as it stood on 31 October. Nothing from another lab is needed.
#
# **Tasks**
# - [ ] 1 · One request: read the page and the cursor (4')
# - [ ] 2 · Follow every page, back off on 429 (7')
# - [ ] 3 · Load with a key and a stored cursor (8')
# - [ ] 4 · Run it twice, then after new data (6')
# - [ ] ✱ Stretch · Keep the rows and the cursor in one transaction

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

api = Q.SupplierAPI(release=1)
print("supplier API at", api.url)

# %% [markdown]
# ## 1 · One request: read the page and the cursor (4')

# %%
import json
import time

import requests

r = requests.get(f"{api.url}/prices", params={"updated_since": ""}, timeout=10)
print(r.status_code, r.headers.get("Content-Type"))
body = r.json()
print(len(body["data"]), "records | next_cursor:", body["next_cursor"])
print(json.dumps(body["data"][0], ensure_ascii=False, indent=1))

# %% [markdown]
# 🔍 The cursor is opaque: do not parse it, send it back. `updated_at` is what makes the load incremental.

# %% [markdown]
# ## 2 · Follow every page, back off on 429 (7')
#
# ✏️ **Exercise** · Write `fetch_since(base_url, since)`: request `/prices?updated_since=<since>`, then keep
# requesting with `cursor=<next_cursor>` until it is `null`. On a `429`, wait `Retry-After` seconds and repeat the
# same request; on any other error, raise. Return all records and the number of 429s you met.

# %%
def fetch_since(base_url: str, since: str = "") -> tuple[list[dict], int]:
    # BEGIN SOLUTION
    records, throttled, params = [], 0, {"updated_since": since}
    while True:
        resp = requests.get(f"{base_url}/prices", params=params, timeout=10)
        if resp.status_code == 429:
            throttled += 1
            time.sleep(float(resp.headers.get("Retry-After", "1")))
            continue
        resp.raise_for_status()
        page = resp.json()
        records += page["data"]
        if not page["next_cursor"]:
            return records, throttled
        params = {"cursor": page["next_cursor"]}
    # END SOLUTION


# %%
def reference_fetch(base_url, since=""):  # safety net: the same logic, supplied
    out, n, params = [], 0, {"updated_since": since}
    while True:
        resp = requests.get(f"{base_url}/prices", params=params, timeout=10)
        if resp.status_code == 429:
            n += 1; time.sleep(float(resp.headers["Retry-After"])); continue
        resp.raise_for_status(); page = resp.json(); out += page["data"]
        if not page["next_cursor"]:
            return out, n
        params = {"cursor": page["next_cursor"]}


try:
    records, throttled = fetch_since(api.url)
except NotImplementedError:
    fetch_since = reference_fetch
    records, throttled = fetch_since(api.url)
print(len(records), "records,", throttled, "times throttled,", api.requests, "requests so far")
Q.check(len(records) == 99 and len({r["price_id"] for r in records}) == 99, "every page of release 1: 99 records")

# %% [markdown]
# ## 3 · Load with a key and a stored cursor (8')
#
# Two decisions make a load safe to repeat:
# - **a key**: one record version is `(price_id, updated_at)`; a version already loaded is not loaded again;
# - **the cursor stored with the data**: the highest `updated_at` loaded, in a table of the same database, so the
#   next run asks only for what is newer.
#
# ✏️ **Exercise** · Write `load(con, base_url)`: read the stored cursor from `raw._load_state` (empty string when
# there is none), fetch since it, insert the new versions into `raw.supplier_prices` without duplicates
# (`INSERT OR IGNORE` with a primary key, or an anti-join), store the new cursor, and return how many rows were
# inserted.

# %%
DB = Q.lab_dir("D2_1") / "qafila.duckdb"
con = Q.connect(DB)
con.execute("CREATE SCHEMA IF NOT EXISTS raw")
con.execute("""CREATE TABLE IF NOT EXISTS raw.supplier_prices (
    price_id VARCHAR, product_id VARCHAR, supplier_name VARCHAR, cost VARCHAR, currency VARCHAR, unit VARCHAR,
    valid_from DATE, updated_at TIMESTAMPTZ, incoterm VARCHAR, loaded_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (price_id, updated_at))""")
con.execute("CREATE TABLE IF NOT EXISTS raw._load_state (source VARCHAR PRIMARY KEY, cursor VARCHAR, updated TIMESTAMPTZ)")
COLS = ["price_id", "product_id", "supplier_name", "cost", "currency", "unit", "valid_from", "updated_at", "incoterm"]


def load(con, base_url: str) -> int:
    # BEGIN SOLUTION
    row = con.execute("SELECT cursor FROM raw._load_state WHERE source = 'supplier_prices'").fetchall()
    since = row[0][0] if row else ""
    new, _ = fetch_since(base_url, since)
    before = con.execute("SELECT count(*) FROM raw.supplier_prices").fetchall()[0][0]
    if new:
        con.executemany(f"INSERT OR IGNORE INTO raw.supplier_prices ({', '.join(COLS)}) VALUES ({', '.join('?' * len(COLS))})",
                        [[r.get(c) for c in COLS] for r in new])
        cursor = max(r["updated_at"] for r in new)
        con.execute("INSERT OR REPLACE INTO raw._load_state VALUES ('supplier_prices', ?, now())", [cursor])
    return con.execute("SELECT count(*) FROM raw.supplier_prices").fetchall()[0][0] - before
    # END SOLUTION


# %%
def reference_load(con, base_url):  # safety net
    row = con.execute("SELECT cursor FROM raw._load_state WHERE source = 'supplier_prices'").fetchall()
    new, _ = fetch_since(base_url, row[0][0] if row else "")
    before = con.execute("SELECT count(*) FROM raw.supplier_prices").fetchall()[0][0]
    if new:
        con.executemany(f"INSERT OR IGNORE INTO raw.supplier_prices ({', '.join(COLS)}) VALUES ({', '.join('?' * len(COLS))})",
                        [[r.get(c) for c in COLS] for r in new])
        con.execute("INSERT OR REPLACE INTO raw._load_state VALUES ('supplier_prices', ?, now())", [max(r["updated_at"] for r in new)])
    return con.execute("SELECT count(*) FROM raw.supplier_prices").fetchall()[0][0] - before


try:
    first = load(con, api.url)
except NotImplementedError:
    load = reference_load
    first = load(con, api.url)
print("first run inserted", first)
print(con.sql("SELECT * FROM raw._load_state"))
Q.check(first == 99, "the first run loads release 1: 99 versions")

# %% [markdown]
# ## 4 · Run it twice, then after new data (6')

# %%
requests_before = api.requests
second = load(con, api.url)
print("second run inserted", second, "using", api.requests - requests_before, "request(s)")
Q.check(second == 0, "a re-run adds nothing")

api.stop()
api = Q.SupplierAPI(release=2)          # two weeks later: new prices and corrections
third = load(con, api.url)
print("after new data inserted", third)
latest = con.sql("""SELECT price_id, cost, updated_at FROM raw.supplier_prices
                    QUALIFY row_number() OVER (PARTITION BY price_id ORDER BY updated_at DESC) = 1""")
corrected = con.execute("SELECT count(*) FROM (SELECT price_id FROM raw.supplier_prices GROUP BY 1 HAVING count(*) > 1)").fetchall()[0][0]
n_latest = con.execute("SELECT count(*) FROM (SELECT DISTINCT price_id FROM raw.supplier_prices)").fetchall()[0][0]
print(f"{n_latest} prices, {corrected} of them corrected (two versions kept)")
Q.check(third == 28 and n_latest == 102 and corrected == 25, "28 new versions: 3 new prices and 25 corrections, history kept")
api.stop()

# %% [markdown]
# 🔍 Raw keeps **every version**: the correction does not overwrite the first price. Staging (Lab 2.2 and Day 3)
# picks the latest version per `price_id`. Why keep both in raw?

# %% [markdown]
# ## ✱ Stretch · Rows and cursor in one transaction
#
# If the process dies between inserting rows and storing the cursor, the next run fetches those rows again (safe,
# thanks to the key). If it stored the cursor first and died before the rows, data would be lost. Wrap both in one
# transaction and prove that a failure leaves neither.

# %%
# BEGIN SOLUTION
api = Q.SupplierAPI(release=2)
con.execute("DELETE FROM raw._load_state")
con.execute("DELETE FROM raw.supplier_prices WHERE updated_at >= TIMESTAMPTZ '2026-10-16 00:00:00+03'")
try:
    con.execute("BEGIN TRANSACTION")
    new, _ = fetch_since(api.url, "2026-10-15T23:59:59+03:00")
    con.executemany(f"INSERT OR IGNORE INTO raw.supplier_prices ({', '.join(COLS)}) VALUES ({', '.join('?' * len(COLS))})",
                    [[r.get(c) for c in COLS] for r in new])
    raise RuntimeError("the process died before storing the cursor")
except RuntimeError as e:
    con.execute("ROLLBACK")
    print("rolled back:", e)
rows_after = con.execute("SELECT count(*) FROM raw.supplier_prices").fetchall()[0][0]
Q.check(rows_after == 99, "a failed transaction leaves neither the rows nor the cursor")
api.stop()
# END SOLUTION

# %% [markdown]
# ## Checkpoint
#
# 1. A re-run doubles the rows. Which decision was missing?
#    <details><summary>Answer</summary>A key for one record version, enforced on insert (or a merge on it). The
#    stored cursor alone is not enough: a crash before storing it re-fetches the same pages.</details>
# 2. Why is the cursor stored in the database, not in a local file?
#    <details><summary>Answer</summary>So that it changes together with the data: a restore of the database restores
#    the matching cursor, and two machines running the load read the same state.</details>
# 3. The API filter is `updated_at > cursor`. Which records can that miss, and how do you guard against it?
#    <details><summary>Answer</summary>Records written later with the same <code>updated_at</code> as the cursor, or
#    a clock that runs behind. Re-read a small overlap (cursor minus a few minutes) and let the key drop what was
#    already loaded.</details>
#
# **Carry forward.** Lab 2.2 does the same load with an ingestion library and compares what it stores.
