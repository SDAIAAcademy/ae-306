# %% [markdown]
# # Lab 4.2 · One node or a local cluster
#
# Day 4 · Session 2 (Distributed processing when measured) · 25 min. Someone proposes moving Qafila's pipeline to a
# distributed engine "for scale". In this lab you run the heaviest transformation, the margin join of every order
# line to the price valid on its date, on DuckDB and on Dask with a local cluster, read Dask's task graph, and compare
# run time and peak memory at two data sizes. The decision comes from the numbers.
#
# **AI-tutor.** An AI assistant may give hints in this lab; it does not write your queries, models or tests.
#
# **Reference state.** `Q.warehouse()` and `Q.build_models(con, names=...)`: the staged lines (confirmed, one copy
# each) and the price list. The lines are repeated to make two sizes. Spark is the production example on the
# slides; it needs a Java runtime, so the lab uses Dask, which is pure Python and runs on a laptop or in Colab.
#
# **Tasks**
# - [ ] 1 · The heaviest transformation on one node (5')
# - [ ] 2 · The same on a local cluster (8')
# - [ ] 3 · Read the task graph: where is the shuffle? (5')
# - [ ] 4 · Time and memory at two sizes (7')
# - [ ] ✱ Stretch · Find the size at which the cluster wins on your laptop

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

import gc
import threading
import time
import warnings

import duckdb
import pandas as pd
import psutil

warnings.filterwarnings("ignore")
con = Q.warehouse()
Q.build_models(con, names=["stg_orders", "stg_order_lines", "stg_products", "stg_prices"])
base = con.sql("""
    SELECT l.order_id, l.line_no, o.order_date, l.product_id,
           l.qty * CASE WHEN l.unit = 'carton' THEN p.units_per_carton ELSE 1 END AS qty_pieces,
           CAST(l.qty * l.unit_price_sar * (1 - l.discount_pct / 100) AS DOUBLE) AS revenue
    FROM stg.order_lines l JOIN stg.orders o ON o.order_id = l.order_id AND o.status = 'confirmed'
    JOIN stg.products p USING (product_id)""").df()
prices = con.sql("SELECT product_id, CAST(cost_piece_sar AS DOUBLE) AS cost_piece_sar, valid_from, valid_to FROM stg.prices").df()
for c in ("order_date", "valid_from", "valid_to"):
    (base if c == "order_date" else prices)[c] = pd.to_datetime((base if c == "order_date" else prices)[c])
SIZES = Q.pick([10, 60], [2, 8])


def lines_at(scale: int) -> pd.DataFrame:
    return pd.concat([base.assign(order_id=base.order_id + k * 1_000_000) for k in range(scale)], ignore_index=True)


class PeakMemory:
    """Peak resident memory of this process while the block runs, sampled every 10 ms."""

    def __enter__(self):
        gc.collect()
        self.proc, self.start, self.peak, self.run = psutil.Process(), psutil.Process().memory_info().rss, 0, True
        threading.Thread(target=self._sample, daemon=True).start()
        self.t = time.perf_counter()
        return self

    def _sample(self):
        while self.run:
            self.peak = max(self.peak, self.proc.memory_info().rss)
            time.sleep(0.01)

    def __exit__(self, *exc):
        self.seconds = time.perf_counter() - self.t
        self.run = False
        time.sleep(0.02)
        self.mb = max(0, self.peak - self.start) / 1e6


print(f"{len(base):,} lines at scale 1; sizes: {SIZES}")

# %% [markdown]
# ## 1 · The heaviest transformation on one node (5')
#
# ✏️ **Exercise** · Write `duck_margin(lines)`: join each line to the price valid on its `order_date`, compute cost
# (`qty_pieces * cost_piece_sar`) and return revenue, cost and margin per month as a DataFrame sorted by month.
# DuckDB can query the pandas frames `lines` and `prices` by name.

# %%
def duck_margin(lines: pd.DataFrame) -> pd.DataFrame:
    # BEGIN SOLUTION
    return duckdb.sql("""
        SELECT strftime(l.order_date, '%Y-%m') AS month, round(sum(l.revenue), 2) AS revenue,
               round(sum(l.qty_pieces * p.cost_piece_sar), 2) AS cost,
               round(sum(l.revenue) - sum(l.qty_pieces * p.cost_piece_sar), 2) AS margin
        FROM lines l JOIN prices p
          ON p.product_id = l.product_id AND l.order_date BETWEEN p.valid_from AND p.valid_to
        GROUP BY 1 ORDER BY 1""").df()
    # END SOLUTION


# %%
try:
    one = duck_margin(base)
except NotImplementedError:  # safety net
    def duck_margin(lines):
        return duckdb.sql("""SELECT strftime(l.order_date, '%Y-%m') AS month, round(sum(l.revenue), 2) AS revenue,
            round(sum(l.qty_pieces * p.cost_piece_sar), 2) AS cost, round(sum(l.revenue) - sum(l.qty_pieces * p.cost_piece_sar), 2) AS margin
            FROM lines l JOIN prices p ON p.product_id = l.product_id AND l.order_date BETWEEN p.valid_from AND p.valid_to
            GROUP BY 1 ORDER BY 1""").df()
    one = duck_margin(base)
print(one.to_string(index=False))
ref = {r["month"]: r["margin"] for r in Q.reference("finance_answers")["q1_monthly"]}
Q.check(all(abs(r.margin - ref[r.month]) < 1 for r in one.itertuples()), "one node reproduces finance's monthly margin")

# %% [markdown]
# ## 2 · The same on a local cluster (8')
#
# Dask splits a dataframe into **partitions** and runs tasks on **workers**. A local cluster runs the workers on
# your laptop: the same code would run on many machines.
#
# ✏️ **Exercise** · Write `dask_margin(lines, npartitions)`: a Dask dataframe from `lines`, merged with `prices` on
# `product_id`, filtered to the valid date range, with `cost` and `month` added, then summed by month. Return a
# pandas DataFrame like `duck_margin`'s (call `.compute()` at the end only).

# %%
import dask
import dask.dataframe as dd
from dask.distributed import Client, LocalCluster

cluster = LocalCluster(n_workers=2, threads_per_worker=2, processes=False, dashboard_address=None)
client = Client(cluster)
print(client)


def dask_frame(lines: pd.DataFrame, npartitions: int = 8):
    # BEGIN SOLUTION
    d = dd.from_pandas(lines, npartitions=npartitions)
    m = d.merge(prices, on="product_id", how="inner")
    m = m[(m.order_date >= m.valid_from) & (m.order_date <= m.valid_to)]
    m = m.assign(cost=m.qty_pieces * m.cost_piece_sar, month=m.order_date.dt.strftime("%Y-%m"))
    return m.groupby("month")[["revenue", "cost"]].sum()
    # END SOLUTION


def dask_margin(lines: pd.DataFrame, npartitions: int = 8) -> pd.DataFrame:
    out = dask_frame(lines, npartitions).compute().sort_index().reset_index()
    out["margin"] = out.revenue - out.cost
    return out.round(2)


# %%
try:
    two = dask_margin(base)
except NotImplementedError:  # safety net
    def dask_frame(lines, npartitions=8):
        d = dd.from_pandas(lines, npartitions=npartitions).merge(prices, on="product_id")
        d = d[(d.order_date >= d.valid_from) & (d.order_date <= d.valid_to)]
        d = d.assign(cost=d.qty_pieces * d.cost_piece_sar, month=d.order_date.dt.strftime("%Y-%m"))
        return d.groupby("month")[["revenue", "cost"]].sum()
    two = dask_margin(base)
print(two.to_string(index=False))
Q.check((two.margin - one.margin).abs().max() < 1, "the cluster gives the same answer")

# %% [markdown]
# ## 3 · Read the task graph: where is the shuffle? (5')
#
# A **shuffle** moves rows between partitions so that rows with the same key meet: it is the expensive, network-heavy
# step of any distributed engine. Joins and group-bys may need one.

# %%
plan = dask_frame(base)
graph = dict(plan.__dask_graph__())
names = pd.Series([k[0] if isinstance(k, tuple) else str(k) for k in graph]).str.replace(r"-[0-9a-f]{8,}.*$", "", regex=True)
print(len(graph), "tasks; by kind:")
print(names.value_counts().head(12).to_string())
try:
    print(plan.optimize().pprint())
except Exception:  # noqa: BLE001 - printing the expression tree differs between Dask releases
    pass

# %% [markdown]
# 🔍 The price list is one small partition, so Dask **broadcasts** it to every partition of the lines: no shuffle
# for the join. The group-by by month is a tree reduction: each partition sums its months, then the partial sums
# combine. On a cluster, a join of two large tables would need a full shuffle, which is what makes it slow.

# %% [markdown]
# ## 4 · Time and memory at two sizes (7')
#
# ✏️ **Exercise** · For each size in `SIZES`, build `lines_at(size)` and measure both engines inside `PeakMemory()`.
# Collect rows of `{"lines", "engine", "seconds", "peak MB"}` in `measured`.

# %%
measured = []
# BEGIN SOLUTION
for size in SIZES:
    lines = lines_at(size)
    for engine, fn in (("DuckDB, one node", duck_margin), ("Dask, local cluster", dask_margin)):
        with PeakMemory() as m:
            fn(lines)
        measured.append({"lines": len(lines), "engine": engine, "seconds": round(m.seconds, 2), "peak MB": round(m.mb)})
    del lines
# END SOLUTION

# %%
if not measured:  # safety net
    for size in SIZES:
        lines = lines_at(size)
        for engine, fn in (("DuckDB, one node", duck_margin), ("Dask, local cluster", dask_margin)):
            with PeakMemory() as m:
                fn(lines)
            measured.append({"lines": len(lines), "engine": engine, "seconds": round(m.seconds, 2), "peak MB": round(m.mb)})
table = pd.DataFrame(measured)
print(table.to_string(index=False))
pivot = table.pivot(index="lines", columns="engine", values="seconds")
Q.check(len(table) == 4, "two engines measured at two sizes")
print("\nDuckDB faster at every size:", bool((pivot["DuckDB, one node"] < pivot["Dask, local cluster"]).all()))
print(f"laptop memory: {psutil.virtual_memory().total / 1e9:.0f} GB")

# %% [markdown]
# ✏️ Write the decision for Qafila in two sentences in the cell below: which engine, up to what size, and what
# measurement would make you change it.

# %% [markdown]
# *Your decision here.*

# %% [markdown]
# ## ✱ Stretch · The size at which the cluster wins
#
# Double the size until Dask is faster than DuckDB or the laptop runs short of memory. Which comes first?

# %%
# BEGIN SOLUTION
size, rows = SIZES[-1], []
while size <= Q.pick(240, 16):
    lines = lines_at(size)
    for engine, fn in (("duckdb", duck_margin), ("dask", dask_margin)):
        with PeakMemory() as m:
            fn(lines)
        rows.append({"lines": len(lines), "engine": engine, "seconds": round(m.seconds, 2)})
    del lines
    size *= 2
print(pd.DataFrame(rows).pivot(index="lines", columns="engine", values="seconds"))
# END SOLUTION
client.close()
cluster.close()

# %% [markdown]
# ## Checkpoint
#
# 1. 3 GB of order lines, a 16 GB laptop. Which engine?
#    <details><summary>Answer</summary>One node: the data fits in memory several times over, and an in-process
#    engine has no tasks to schedule and no data to move between workers.</details>
# 2. What does a shuffle cost, and when can a join avoid one?
#    <details><summary>Answer</summary>Every row crosses the network (or the process boundary) once. A join with a
#    small table avoids it by broadcasting the small table to every partition.</details>
# 3. What would justify a cluster for Qafila?
#    <details><summary>Answer</summary>Data that no longer fits one machine's memory and disk, or a deadline one
#    machine cannot meet, shown by a measurement like this one, not by habit.</details>
#
# **Carry forward.** Nothing: the capstone runs on one node.
