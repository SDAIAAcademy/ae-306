# %% [markdown]
# # Setup check
#
# Run this once before Day 1 (3 to 5 minutes). It installs the packages on Colab, generates Qafila's synthetic data,
# checks the package versions and runs a short smoke test of the tools the labs use. No model, no API key, no Docker
# and no cloud account are needed.
#
# Locally: `cd labs && uv sync && uv run jupyter lab`. On Colab: run the cells; a CPU runtime is enough.

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
Q.ensure_data()
print("data:", Q.RAW.relative_to(Q.LABS).as_posix(), "| quick mode:", Q.QUICK)

# %% [markdown]
# ## 1 · Packages

# %%
import platform
from importlib.metadata import PackageNotFoundError, version

import pandas as pd

rows = []
for name in ["duckdb", "polars", "pyarrow", "pandas", "dlt", "sqlmesh", "pyiceberg", "dagster", "dask", "psutil"]:
    try:
        rows.append((name, version(name)))
    except PackageNotFoundError:
        rows.append((name, "MISSING"))
print("Python", platform.python_version(), "|", platform.system(), "| CPUs:", os.cpu_count())
Q.check(all(v != "MISSING" for _, v in rows), "every package the labs use is installed")
pd.DataFrame(rows, columns=["package", "version"])

# %% [markdown]
# ## 2 · Qafila's data
#
# The sources are synthetic and generated with a fixed seed by `qafila_data.py`: no real personal data.

# %%
import duckdb

con = duckdb.connect()
counts = {p.stem: con.sql(f"SELECT count(*) FROM read_csv('{Q.posix(p)}')").fetchall()[0][0]
          for p in sorted(Q.EXTRACTS.glob("*.csv"))}
counts["supplier change events"] = con.sql(
    f"SELECT count(*) FROM read_json('{Q.posix(Q.RAW / 'suppliers' / 'supplier_changes.jsonl')}', format = 'newline_delimited')"
).fetchall()[0][0]
con.close()
Q.check(len(counts) >= 5 and all(n > 0 for n in counts.values()), "the extracts and the change feed are readable")
pd.DataFrame(counts.items(), columns=["source", "rows"])

# %% [markdown]
# ## 3 · Smoke test: the supplier API, Polars and Iceberg

# %%
import polars as pl
import pyarrow as pa
import requests
from pyiceberg.catalog.sql import SqlCatalog

api = Q.SupplierAPI(release=1)
page = requests.get(f"{api.url}/prices", timeout=10).json()
api.stop()
Q.check(len(page["data"]) > 0, f"the local supplier API answered with {len(page['data'])} prices")

df = pl.DataFrame({"city": ["Jeddah", "Riyadh", "Dammam"], "orders": [3, 2, 1]})
Q.check(df["orders"].sum() == 6, "Polars works")

lab = Q.lab_dir("00_setup")
catalog = SqlCatalog("smoke", uri=f"sqlite:///{Q.posix(lab)}/catalog.db", warehouse=Q.posix(lab))
catalog.create_namespace_if_not_exists("smoke")
table = catalog.create_table("smoke.cities", schema=df.to_arrow().schema)
table.append(df.to_arrow())
Q.check(table.scan().to_arrow().num_rows == 3, "PyIceberg wrote a table and read it back")

# %% [markdown]
# ## You're ready
#
# If every check printed ✅, go to Lab 1.1. If a package is missing, run `uv sync` again (locally) or re-run the
# first cell (Colab). On Windows, if an import fails with "The filename or extension is too long", see
# `labs/README.md`.
