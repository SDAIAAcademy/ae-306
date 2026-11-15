# %% [markdown]
# # Lab 3.2 · Models, environments and a state-aware rebuild
#
# Day 3 · Session 2 (Transformations as code) · 25 min. Lab 3.1's tables were statements typed into a notebook.
# Here they become a project: one SQL file per model, in git, built by SQLMesh into a development environment,
# promoted to production, and rebuilt after a change only where the change reaches.
#
# **AI-tutor.** An AI assistant may give hints in this lab; it does not write your queries, models or tests.
#
# **Reference state.** `labs/models/*.sql`: Qafila's staging and mart models (Lab 3.1's tables) with a SQLMesh
# `MODEL (...)` header each, and `Q.warehouse(path)`, which writes the raw tables into the project's DuckDB file.
# Nothing from another lab is needed.
#
# **Tasks**
# - [ ] 1 · The project and its first commit (5')
# - [ ] 2 · Write the mart model (6')
# - [ ] 3 · Plan dev, then promote to prod (6')
# - [ ] 4 · Change one model: what rebuilds? (8')
# - [ ] ✱ Stretch · Review an agent-written model: run it against your tests before you trust it

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

import logging
import shutil

logging.getLogger("sqlmesh").setLevel(logging.ERROR)
from sqlmesh import Context
from sqlmesh.core.config import Config, DuckDBConnectionConfig, GatewayConfig, ModelDefaultsConfig

PROJ = Q.lab_dir("D3_2") / "qafila_models"
(PROJ / "models").mkdir(parents=True)
DB = PROJ / "qafila.duckdb"
Q.warehouse(DB).close()                       # raw.* tables, as the nightly load leaves them

# %% [markdown]
# ## 1 · The project and its first commit (5')
#
# A model is a file: a `MODEL (...)` header (name, kind, grain) and one `SELECT`. SQLMesh reads the dependencies
# from the SQL itself: `stg.orders` used in `FROM` means "build stg.orders first".

# %%
for name in Q.MODEL_ORDER:
    if name != "margin_monthly":              # step 2 writes this one
        shutil.copy(Q.MODELS / f"{name}.sql", PROJ / "models" / f"{name}.sql")
print((PROJ / "models" / "stg_order_lines.sql").read_text(encoding="utf-8"))


def git(*args):
    out = subprocess.run(["git", *args], cwd=PROJ, capture_output=True, text=True)
    return (out.stdout + out.stderr).strip()


git("init", "-q", "-b", "main")
assert (PROJ / ".git").is_dir(), "git init did not create a repository here: stop, or the commits below would go into the enclosing repository"
(PROJ / ".gitignore").write_text("*.duckdb\n*.wal\n.cache/\nlogs/\n", encoding="utf-8")
git("add", ".")
print(git("-c", "user.name=Qafila data team", "-c", "user.email=data@qafila.example", "commit", "-q", "-m", "Staging and dimension models"))
print(git("log", "--oneline"))

# %% [markdown]
# ## 2 · Write the mart model (6')
#
# ✏️ **Exercise** · Write `models/margin_monthly.sql`: a `MODEL (name mart.margin_monthly, kind FULL, grain month);`
# header, then month, revenue, cost, margin and margin percent from `mart.fct_order_line`, rounded to 2 decimals.

# %%
# BEGIN SOLUTION
(PROJ / "models" / "margin_monthly.sql").write_text("""MODEL (name mart.margin_monthly, kind FULL, grain month);

SELECT
  strftime(order_date, '%Y-%m') AS month,
  round(sum(revenue), 2) AS revenue,
  round(sum(cost), 2) AS cost,
  round(sum(revenue) - sum(cost), 2) AS margin,
  round(100 * (sum(revenue) - sum(cost)) / sum(revenue), 2) AS margin_pct
FROM mart.fct_order_line
GROUP BY 1
ORDER BY 1
""", encoding="utf-8")
# END SOLUTION

# %%
if not (PROJ / "models" / "margin_monthly.sql").exists():  # safety net
    shutil.copy(Q.MODELS / "margin_monthly.sql", PROJ / "models" / "margin_monthly.sql")
git("add", ".")
git("-c", "user.name=Qafila data team", "-c", "user.email=data@qafila.example", "commit", "-q", "-m", "Monthly margin mart")
CONFIG = Config(gateways={"local": GatewayConfig(connection=DuckDBConnectionConfig(database=str(DB)))},
                default_gateway="local", model_defaults=ModelDefaultsConfig(dialect="duckdb"))


def context() -> Context:
    return Context(paths=str(PROJ), config=CONFIG)


ctx = context()
print(sorted(ctx.models))
print("upstream of mart.margin_monthly:", sorted(ctx.dag.upstream('"qafila"."mart"."margin_monthly"')))

# %% [markdown]
# ## 3 · Plan dev, then promote to prod (6')
#
# A **plan** compares the project with what each environment holds and lists what must be built. `dev` gets its
# own views (`stg__dev`, `mart__dev`); production is untouched until you promote.
#
# ✏️ **Exercise** · Apply a plan to `dev`, then one to production (`ctx.plan(...)` with no environment). Keep the two
# plans in `plan_dev` and `plan_prod`. Use `auto_apply=True, no_prompts=True`.

# %%
# BEGIN SOLUTION
plan_dev = ctx.plan("dev", auto_apply=True, no_prompts=True)
plan_prod = ctx.plan(auto_apply=True, no_prompts=True)
# END SOLUTION

# %%
try:
    plan_dev, plan_prod
except NameError:  # safety net
    plan_dev = ctx.plan("dev", auto_apply=True, no_prompts=True)
    plan_prod = ctx.plan(auto_apply=True, no_prompts=True)
built_dev = sorted(s.snapshot_id.name for s in plan_dev.missing_intervals)
built_prod = sorted(s.snapshot_id.name for s in plan_prod.missing_intervals)
print(f"dev built {len(built_dev)} models; promoting to prod built {len(built_prod)}")
prod = ctx.fetchdf("SELECT * FROM mart.margin_monthly ORDER BY month")
print(prod.to_string(index=False))
ref = Q.reference("finance_answers")["q1_monthly"]
Q.check(len(built_dev) == 11 and len(built_prod) == 0, "dev built all 11 models; promotion rebuilt nothing (it swapped views)")
Q.check(all(abs(float(r.margin) - x["margin"]) < 1 for r, x in zip(prod.itertuples(), ref)), "production's margin equals finance's reference")

# %% [markdown]
# 🔍 Promotion was free: production's views now point at the tables dev already built. That is what "virtual
# environments" means.

# %% [markdown]
# ## 4 · Change one model: what rebuilds? (8')
#
# Two changes, two answers:
# - **non-breaking**: add a column to `stg_products` (nothing downstream reads it);
# - **breaking**: change the rows of `stg_orders` (every model downstream may change).
#
# ✏️ **Exercise** · Make each change in its file, plan `dev`, and record which models the plan rebuilds in
# `rebuilt_non_breaking` and `rebuilt_breaking` (sets of model names).

# %%
def rebuilt(plan) -> set[str]:
    return {s.snapshot_id.name.split(".")[-1].strip('"') for s in plan.missing_intervals}


def edit(model: str, old: str, new: str):
    f = PROJ / "models" / f"{model}.sql"
    text = f.read_text(encoding="utf-8")
    assert old in text, old
    f.write_text(text.replace(old, new), encoding="utf-8")


# BEGIN SOLUTION
edit("stg_products", "AS list_price_piece_sar", "AS list_price_piece_sar,\n       upper(category) AS category_code")
plan = context().plan("dev", auto_apply=True, no_prompts=True)
rebuilt_non_breaking = rebuilt(plan)
edit("stg_orders", "FROM raw.orders", "FROM raw.orders\nWHERE CAST(order_date AS DATE) >= DATE '2026-08-01'")
plan = context().plan("dev", auto_apply=True, no_prompts=True)
rebuilt_breaking = rebuilt(plan)
# END SOLUTION

# %%
try:
    rebuilt_non_breaking, rebuilt_breaking
except NameError:  # safety net
    edit("stg_products", "AS list_price_piece_sar", "AS list_price_piece_sar,\n       upper(category) AS category_code")
    rebuilt_non_breaking = rebuilt(context().plan("dev", auto_apply=True, no_prompts=True))
    edit("stg_orders", "FROM raw.orders", "FROM raw.orders\nWHERE CAST(order_date AS DATE) >= DATE '2026-08-01'")
    rebuilt_breaking = rebuilt(context().plan("dev", auto_apply=True, no_prompts=True))
print("add a column to stg_products ->", sorted(rebuilt_non_breaking))
print("change the rows of stg_orders ->", sorted(rebuilt_breaking))
print(git("diff", "--stat"))
Q.check(rebuilt_non_breaking == {"products"}, "a non-breaking change rebuilds only the model that changed")
Q.check({"orders", "fct_order_line", "margin_monthly"} <= rebuilt_breaking and "customers" not in rebuilt_breaking,
        "a breaking change rebuilds the model and what reads it, and skips the rest")

# %% [markdown]
# 🔍 `git diff` shows the change you made; the plan shows what it costs. Review both before promoting.

# %% [markdown]
# ## ✱ Stretch · Review an agent-written model
#
# An assistant wrote this model for "margin by product". It looks right. Run the two tests that matter here, the
# grain (one row per product) and the reconciliation (its total equals the monthly mart), before you trust it.

# %%
# BEGIN SOLUTION
AGENT_SQL = """
SELECT l.product_id, sum(l.qty * l.unit_price_sar) AS revenue,
       sum(l.qty * CASE WHEN l.unit = 'carton' THEN p.units_per_carton ELSE 1 END * pr.cost_piece_sar) AS cost
FROM stg.order_lines l
JOIN stg.orders o USING (order_id)
JOIN stg.products p USING (product_id)
JOIN stg.prices pr USING (product_id)
GROUP BY 1"""
agent = ctx.fetchdf(AGENT_SQL)
total_agent = float(agent.revenue.sum())
total_mart = float(ctx.fetchdf("SELECT sum(revenue) AS r FROM mart.margin_monthly").r[0])
print(f"rows {len(agent)} for {agent.product_id.nunique()} products | revenue {total_agent:,.0f} against the mart's {total_mart:,.0f}")
print("Three defects: the join to prices ignores the dates (one row per price version), cancelled orders are kept,"
      " and the discount is missing. The grain test passes; the reconciliation does not.")
# END SOLUTION

# %% [markdown]
# ## Checkpoint
#
# 1. You change one staging model. What does SQLMesh rebuild?
#    <details><summary>Answer</summary>That model, and the models downstream of it only if the change is breaking
#    (it changes rows or columns they read). A new column nobody reads rebuilds one model.</details>
# 2. Why did promoting to production cost nothing?
#    <details><summary>Answer</summary>Production's views were pointed at the tables built for dev, which held the
#    same model versions. No data moved.</details>
# 3. What should you run before accepting a model an assistant wrote?
#    <details><summary>Answer</summary>The project's tests and a reconciliation with a trusted number. A query that
#    runs and has the right grain can still be wrong.</details>
#
# **Carry forward.** The models in `labs/models/` are the capstone's starting point.
