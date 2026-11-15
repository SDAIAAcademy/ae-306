# %% [markdown]
# # Lab 3.4 · Assets, a failure, a retry and a backfill
#
# Day 3 · Session 4 (Orchestration) · 25 min. Qafila's pipeline now has parts: a supplier load, a contract, a price
# table, the fact and the monthly margin. In this lab you declare them as Dagster assets with their dependencies,
# put them on a nightly schedule, watch a retry policy absorb a flaky API, let the contract check **block** the refresh when the November batch
# breaks, fix the feed and backfill one month of the margin.
#
# **AI-tutor.** An AI assistant may give hints in this lab; it does not write your queries, models or tests.
#
# **Reference state.** `Q.warehouse(path)` and the models in `labs/models/` (the star of Lab 3.1),
# `contracts/supplier_prices.odcs.yaml` and `contract_gate.py` (Lab 3.3), `Q.SupplierAPI` (Lab 2.1). Runs execute in
# this notebook with a temporary Dagster instance: no server, no daemon. The schedule is declared and inspected;
# with no daemon to fire it, you launch each run by hand, as an operator would launch a run from the schedule's job.
#
# **Tasks**
# - [ ] 1 · Assets, their graph and a schedule (6')
# - [ ] 2 · A flaky source and a retry policy (5')
# - [ ] 3 · The broken feed: the check blocks the mart (7')
# - [ ] 4 · Fix, then backfill one month (7')
# - [ ] ✱ Stretch · Emit lineage events for each run

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

import logging
import warnings

warnings.filterwarnings("ignore")
WORK = Q.lab_dir("D3_4")
os.environ["DAGSTER_HOME"] = str(WORK / "dagster_home")
(WORK / "dagster_home").mkdir()
logging.getLogger("dagster").setLevel(logging.ERROR)

import dagster as dg
import requests

DB = WORK / "qafila.duckdb"
with Q.warehouse(DB) as _con:
    _con.execute("CREATE VIEW products AS SELECT * FROM raw.products")   # the contract's product_known rule reads it
CONTRACT = G.load(Path("contracts/supplier_prices.odcs.yaml"))
API = Q.SupplierAPI(release=2, fail_first=2, throttle_every=0)   # the first two requests answer 503
BATCH = {"file": "batch_2026-11-01.jsonl"}                        # the November batch the producer sent
QUIET = {"loggers": {"console": {"config": {"log_level": "ERROR"}}}}   # pass as run_config: errors only
print("dagster", dg.__version__)

# %% [markdown]
# ## 1 · Assets, their graph and a schedule (6')
#
# An **asset** is a table the pipeline keeps up to date, declared with the assets it depends on. Dagster builds the
# graph from the declarations and runs each asset after its dependencies.
#
# ✏️ **Exercise** · Declare `current_prices` (depends on `supplier_prices` and `november_batch`) and `fct_order_line`
# (depends on `current_prices`) like the two assets above them. `current_prices` keeps the latest version of each
# price from the October load and the November batch; `fct_order_line` builds the reference models
# (`Q.build_models(con)`).
#
# Below the assets, the cell declares the **schedule**: a job over the four unpartitioned assets and a cron line
# that launches it every night. Read what it prints.

# %%
def db():
    return Q.connect(DB)


def fetch_all(base_url: str) -> list[dict]:
    out, params = [], {"updated_since": ""}
    while True:
        r = requests.get(f"{base_url}/prices", params=params, timeout=10)
        r.raise_for_status()                          # a 503 raises: the retry policy decides what happens next
        page = r.json()
        out += page["data"]
        if not page["next_cursor"]:
            return out
        params = {"cursor": page["next_cursor"]}


@dg.asset(retry_policy=dg.RetryPolicy(max_retries=3, delay=0.2), group_name="ingest")
def supplier_prices(context) -> dg.MaterializeResult:
    """Every price version the supplier API served up to 31 October."""
    rows = fetch_all(API.url)
    with db() as con:
        con.execute("CREATE OR REPLACE TABLE raw.supplier_prices AS SELECT * FROM (SELECT unnest(?, recursive := true))", [rows])
    context.log.info(f"loaded {len(rows)} versions after {context.retry_number} retries")
    return dg.MaterializeResult(metadata={"rows": len(rows), "retries": context.retry_number})


@dg.asset(deps=[supplier_prices], group_name="ingest")
def november_batch() -> dg.MaterializeResult:
    """The producer's November batch, landed as it arrived."""
    with db() as con:
        con.execute(f"CREATE OR REPLACE TABLE raw.november_batch AS SELECT * FROM read_json('{Q.posix(Q.RAW / 'supplier_api' / BATCH['file'])}')")
        n = con.execute("SELECT count(*) FROM raw.november_batch").fetchall()[0][0]
    return dg.MaterializeResult(metadata={"rows": n, "file": BATCH["file"]})


# BEGIN SOLUTION
@dg.asset(deps=[supplier_prices, november_batch], group_name="model")
def current_prices() -> dg.MaterializeResult:
    """The latest version of each price: what the cost side of the margin reads."""
    with db() as con:
        con.execute(G.NUM_MACRO)
        con.execute("""CREATE OR REPLACE TABLE raw.current_prices AS
            SELECT price_id, product_id, num(cost) AS cost, currency, unit, valid_from, updated_at FROM (
              SELECT price_id, product_id, cost, currency, unit, valid_from, updated_at FROM raw.supplier_prices
              UNION ALL
              SELECT price_id, product_id, cost, currency, unit, valid_from, updated_at FROM raw.november_batch)
            QUALIFY row_number() OVER (PARTITION BY price_id ORDER BY updated_at DESC) = 1""")
        n = con.execute("SELECT count(*) FROM raw.current_prices").fetchall()[0][0]
    return dg.MaterializeResult(metadata={"prices": n})


@dg.asset(deps=[current_prices], group_name="model")
def fct_order_line() -> dg.MaterializeResult:
    """The star of Lab 3.1, rebuilt from the reference models."""
    with db() as con:
        built = Q.build_models(con)
        n = con.execute("SELECT count(*) FROM mart.fct_order_line").fetchall()[0][0]
    return dg.MaterializeResult(metadata={"models": len(built), "rows": n})
# END SOLUTION


# %%
try:
    current_prices, fct_order_line
except NameError:  # safety net: the same two assets, supplied
    @dg.asset(deps=[supplier_prices, november_batch], group_name="model")
    def current_prices():
        with db() as con:
            con.execute(G.NUM_MACRO)
            con.execute("""CREATE OR REPLACE TABLE raw.current_prices AS SELECT price_id, product_id, num(cost) AS cost, currency, unit,
                valid_from, updated_at FROM (SELECT price_id, product_id, cost, currency, unit, valid_from, updated_at FROM raw.supplier_prices
                UNION ALL SELECT price_id, product_id, cost, currency, unit, valid_from, updated_at FROM raw.november_batch)
                QUALIFY row_number() OVER (PARTITION BY price_id ORDER BY updated_at DESC) = 1""")
        return dg.MaterializeResult()

    @dg.asset(deps=[current_prices], group_name="model")
    def fct_order_line():
        with db() as con:
            Q.build_models(con)
        return dg.MaterializeResult()

MONTHS = dg.MonthlyPartitionsDefinition(start_date="2026-08-01", end_date="2026-11-01")


@dg.asset(deps=[fct_order_line], partitions_def=MONTHS, group_name="mart")
def margin_monthly(context) -> dg.MaterializeResult:
    """One partition per month: delete the month, insert it again."""
    month = context.partition_key[:7]
    with db() as con:
        con.execute("CREATE TABLE IF NOT EXISTS mart.margin_by_month (month VARCHAR, revenue DECIMAL(18, 2), cost DECIMAL(18, 2), margin DECIMAL(18, 2), built_by VARCHAR)")
        con.execute("DELETE FROM mart.margin_by_month WHERE month = ?", [month])
        con.execute("""INSERT INTO mart.margin_by_month
            SELECT ?, round(sum(revenue), 2), round(sum(cost), 2), round(sum(revenue) - sum(cost), 2), ?
            FROM mart.fct_order_line WHERE strftime(order_date, '%Y-%m') = ?""", [month, context.run_id[:8], month])
        margin = con.execute("SELECT margin FROM mart.margin_by_month WHERE month = ?", [month]).fetchall()[0][0]
    return dg.MaterializeResult(metadata={"month": month, "margin": float(margin)})


@dg.asset_check(asset=november_batch, blocking=True)
def supplier_contract() -> dg.AssetCheckResult:
    """The ODCS contract of Lab 3.3, as a check that blocks everything downstream when it fails."""
    with db() as con:
        results = G.run(con, CONTRACT, "raw.november_batch")
    failed = [r["id"] for r in results if not r["passed"]]
    return dg.AssetCheckResult(passed=not failed, metadata={"failed": ", ".join(failed) or "none"})


ASSETS = [supplier_prices, november_batch, current_prices, fct_order_line, margin_monthly]
# The schedule: a job that selects the four unpartitioned assets, and the cron line that launches it every night.
NIGHTLY = dg.define_asset_job("nightly_refresh", selection=["supplier_prices", "november_batch", "current_prices", "fct_order_line"])
SCHEDULE = dg.ScheduleDefinition(job=NIGHTLY, cron_schedule="0 2 * * *", execution_timezone="Asia/Riyadh")
defs = dg.Definitions(assets=ASSETS, asset_checks=[supplier_contract], jobs=[NIGHTLY], schedules=[SCHEDULE])
graph = defs.resolve_asset_graph()
for key in graph.toposorted_asset_keys:
    print(f"{key.to_user_string():16s} <- {sorted(k.to_user_string() for k in graph.get(key).parent_keys)}")
Q.check(len(graph.toposorted_asset_keys) == 5, "five assets in one graph")
scheduled = defs.resolve_schedule_def("nightly_refresh_schedule")
print(f"schedule {scheduled.name}: cron '{scheduled.cron_schedule}' ({scheduled.execution_timezone}) launches job {scheduled.job_name}")
Q.check(scheduled.job_name == "nightly_refresh", "the nightly schedule launches the refresh job")

# %% [markdown]
# ## 2 · A flaky source and a retry policy (5')
#
# The API answers 503 to its first two requests (a deploy on the supplier's side). `supplier_prices` has
# `RetryPolicy(max_retries=3, delay=0.2)`.
#
# ✏️ **Exercise** · Materialise `supplier_prices` alone with `dg.materialize(...)` and an ephemeral instance
# (`dg.DagsterInstance.ephemeral()`) and `run_config=QUIET`, keeping the result in `run1`. Read how many retries it took.

# %%
instance = dg.DagsterInstance.ephemeral()
# BEGIN SOLUTION
run1 = dg.materialize([supplier_prices], instance=instance, run_config=QUIET)
# END SOLUTION

# %%
try:
    run1
except NameError:  # safety net
    run1 = dg.materialize([supplier_prices], instance=instance, run_config=QUIET)
mat = run1.asset_materializations_for_node("supplier_prices")[0]
print("success:", run1.success, "| metadata:", {k: v.value for k, v in mat.metadata.items()}, "| API requests:", API.requests)
retries = [e for e in run1.all_events if e.event_type_value == "STEP_UP_FOR_RETRY"]
Q.check(run1.success and len(retries) == 2, "two failures absorbed by two retries")

# %% [markdown]
# 🔍 Retry what can succeed on a second try (a timeout, a 503, a 429). Never retry a failed check: the data will
# not fix itself.

# %% [markdown]
# ## 3 · The broken feed: the check blocks the mart (7')
#
# The contract check is **blocking**: when it fails, nothing downstream of `november_batch` runs in that run.

# %%
API.fail_first = 0
run2 = dg.materialize(ASSETS[:4] + [supplier_contract], instance=instance, raise_on_error=False, run_config=QUIET,
                      selection=["supplier_prices", "november_batch", "current_prices", "fct_order_line"])
check = run2.get_asset_check_evaluations()[0]
ran = sorted({e.step_key for e in run2.all_events if e.event_type_value == "STEP_SUCCESS"})
skipped = sorted({e.step_key for e in run2.all_events if e.event_type_value == "STEP_SKIPPED"})
print("check passed:", check.passed, "| failed rules:", check.metadata["failed"].value)
print("steps that ran:", ran)
print("steps not run:", skipped or "(none)", "| run success:", run2.success)
with db() as con:
    exists = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'current_prices'").fetchall()[0][0]

# %% [markdown]
# ✏️ **Exercise** · Write the run-log line that goes to Ammar Basri: what was caught, what was not refreshed, what
# stays in place. Then assert that the price table and the fact were **not** built in this run.

# %%
# BEGIN SOLUTION
run_log = (f"Run {run2.run_id[:8]}: contract qafila-supplier-prices failed on the November batch ({check.metadata['failed'].value}). "
           f"current_prices and fct_order_line were not refreshed; the mart keeps October's prices.")
not_built = {"current_prices", "fct_order_line"}.isdisjoint(ran)
# END SOLUTION

# %%
try:
    run_log, not_built
except NameError:  # safety net
    run_log, not_built = "(write the log line)", {"current_prices", "fct_order_line"}.isdisjoint(ran)
print(run_log)
Q.check(not check.passed and not_built and exists == 0, "the violation was caught and nothing downstream was refreshed")

# %% [markdown]
# ## 4 · Fix, then backfill one month (7')
#
# Ammar's producer sends the fixed batch. Run the pipeline again, then **backfill** October's partition of the
# margin only: a backfill recomputes chosen partitions and leaves the others alone.
#
# ✏️ **Exercise** · Point `BATCH["file"]` at `batch_2026-11-01_fixed.jsonl`, materialise the four unpartitioned
# assets with the check (`run3`), then materialise `margin_monthly` for all three months (`runs_months`, one run per
# partition key) and finally backfill `2026-10-01` again (`run_backfill`).

# %%
# BEGIN SOLUTION
BATCH["file"] = "batch_2026-11-01_fixed.jsonl"
run3 = dg.materialize(ASSETS[:4] + [supplier_contract], instance=instance, run_config=QUIET,
                      selection=["supplier_prices", "november_batch", "current_prices", "fct_order_line"])
runs_months = [dg.materialize([margin_monthly], instance=instance, run_config=QUIET, partition_key=k) for k in MONTHS.get_partition_keys()]
run_backfill = dg.materialize([margin_monthly], instance=instance, run_config=QUIET, partition_key="2026-10-01")
# END SOLUTION

# %%
try:
    run3, runs_months, run_backfill
except NameError:  # safety net
    BATCH["file"] = "batch_2026-11-01_fixed.jsonl"
    run3 = dg.materialize(ASSETS[:4] + [supplier_contract], instance=instance, run_config=QUIET, selection=["supplier_prices", "november_batch", "current_prices", "fct_order_line"])
    runs_months = [dg.materialize([margin_monthly], instance=instance, run_config=QUIET, partition_key=k) for k in MONTHS.get_partition_keys()]
    run_backfill = dg.materialize([margin_monthly], instance=instance, run_config=QUIET, partition_key="2026-10-01")
with db() as con:
    table = con.sql("SELECT * FROM mart.margin_by_month ORDER BY month").df()
print("check passed:", run3.get_asset_check_evaluations()[0].passed)
print(table.to_string(index=False))
ref = {r["month"]: r["margin"] for r in Q.reference("finance_answers")["q1_monthly"]}
Q.check(run3.success and all(abs(float(r.margin) - ref[r.month]) < 1 for r in table.itertuples()), "after the fix every month equals finance's reference")
Q.check(table.set_index("month").built_by["2026-10"] == run_backfill.run_id[:8] and
        table.set_index("month").built_by["2026-08"] != run_backfill.run_id[:8], "the backfill rebuilt October only")
statuses = instance.get_status_by_partition(dg.AssetKey("margin_monthly"), MONTHS.get_partition_keys(), MONTHS)
print("partition status:", {k: str(v).split(".")[-1] for k, v in statuses.items()})

# %% [markdown]
# ## ✱ Stretch · Lineage events for each run
#
# OpenLineage describes a run as events: a job, a run id, its inputs and outputs. Build one event per
# materialisation of `run3` from Dagster's own events and the asset graph.

# %%
# BEGIN SOLUTION
import json

events = []
for e in run3.all_events:
    if e.event_type_value == "ASSET_MATERIALIZATION":
        key = e.asset_key
        events.append({"eventType": "COMPLETE", "run": {"runId": run3.run_id}, "job": {"namespace": "qafila", "name": key.to_user_string()},
                       "inputs": [{"namespace": "qafila", "name": k.to_user_string()} for k in graph.get(key).parent_keys],
                       "outputs": [{"namespace": "qafila", "name": key.to_user_string()}]})
print(json.dumps(events[-1], indent=1))
print(len(events), "lineage events")
# END SOLUTION
API.stop()

# %% [markdown]
# ## Checkpoint
#
# 1. Which failures deserve a retry, and which a block?
#    <details><summary>Answer</summary>Retry transient failures of the transport (timeouts, 503, 429). Block on
#    failed checks of the data: a second try reads the same broken batch.</details>
# 2. Why partition the margin by month?
#    <details><summary>Answer</summary>A late correction to October recomputes October only; the other months, already
#    reported, are not touched, and the run log says which partition changed when.</details>
# 3. The schedule fires every night. What does it launch, and what does it leave out?
#    <details><summary>Answer</summary>The job of the four unpartitioned assets with the blocking check. The monthly
#    margin is partitioned: a month is built by a run for that partition, which is what makes a backfill possible.</details>
# 4. The check blocked the run. What does finance see in the morning?
#    <details><summary>Answer</summary>Yesterday's margin, unchanged and labelled with its last refresh, and the
#    alert to the data owner. Never a margin computed from a feed that broke its contract.</details>
#
# **Carry forward.** The capstone runs this graph from a clean checkout.
