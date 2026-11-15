# %% [markdown]
# # Lab 1.4 · Partitioned columnar files, measured
#
# Day 1 · Session 4 (Columnar files and partitioning) · 25 min. The nightly extracts are CSV files that every
# query reads from the first byte to the last. In this lab you convert the order lines to Parquet, read the
# statistics Parquet keeps per row group, partition the files by month, and measure time and bytes for a query on
# one month. Then you make too many small files on purpose and measure what they cost.
#
# **AI-tutor.** An AI assistant may give hints in this lab; it does not write your queries, models or tests.
#
# **Reference state.** `Q.warehouse()` and `Q.lines_wide(con)`: one row per extract line with its order date, status
# and revenue. To make the measurements visible, the lines are repeated `SCALE` times.
#
# **Tasks**
# - [ ] 1 · CSV against Parquet: size and scan time (6')
# - [ ] 2 · Row groups and their statistics (6')
# - [ ] 3 · Partition by month and query one month (8')
# - [ ] 4 · Too many small files, measured (5')
# - [ ] ✱ Stretch · Prove the pruning in the query plan

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
import pandas as pd

con = Q.warehouse()
Q.lines_wide(con)
SCALE = Q.pick(40, 8)
con.execute(f"""CREATE OR REPLACE TABLE big AS
    SELECT l.* REPLACE (order_id + k * 1000000 AS order_id), strftime(order_date, '%Y-%m') AS month
    FROM lines l, range({SCALE}) t(k) ORDER BY random()""")
N = con.execute("SELECT count(*) FROM big").fetchall()[0][0]
OUT = Q.lab_dir("D1_4")
print(f"{N:,} lines in table big, written under {OUT.name}/")

# %% [markdown]
# ## 1 · CSV against Parquet: size and scan time (6')
#
# ✏️ **Exercise** · Write `big` to `OUT/lines.csv` and to `OUT/lines.parquet` with DuckDB's `COPY ... TO ...`
# (`FORMAT csv, HEADER` and `FORMAT parquet`).

# %%
csv_path, pq_path = Q.posix(OUT / "lines.csv"), Q.posix(OUT / "lines.parquet")
# BEGIN SOLUTION
con.execute(f"COPY big TO '{csv_path}' (FORMAT csv, HEADER)")
con.execute(f"COPY big TO '{pq_path}' (FORMAT parquet)")
# END SOLUTION

# %%
if not (OUT / "lines.parquet").exists():  # safety net
    con.execute(f"COPY big TO '{csv_path}' (FORMAT csv, HEADER)")
    con.execute(f"COPY big TO '{pq_path}' (FORMAT parquet)")
q = "SELECT category, round(sum(revenue)) AS revenue FROM {src} WHERE status = 'confirmed' GROUP BY 1 ORDER BY 1"
t_csv, r_csv = Q.timed(lambda: con.execute(q.format(src=f"read_csv('{csv_path}')")).fetchall())
t_pq, r_pq = Q.timed(lambda: con.execute(q.format(src=f"read_parquet('{pq_path}')")).fetchall())
size = pd.DataFrame({"size": [Q.mb(Q.folder_bytes(OUT / "lines.csv")), Q.mb(Q.folder_bytes(OUT / "lines.parquet"))],
                     "scan (ms)": [round(1000 * t_csv), round(1000 * t_pq)]}, index=["CSV", "Parquet"])
print(size)
Q.check(r_csv == r_pq, "same answer from both files")
Q.check(Q.folder_bytes(OUT / "lines.parquet") < Q.folder_bytes(OUT / "lines.csv") / 3, "Parquet is less than a third of the CSV")

# %% [markdown]
# ## 2 · Row groups and their statistics (6')
#
# A Parquet file is cut into row groups; each keeps the minimum and maximum of every column. A reader skips a row
# group whose range cannot match the filter. The rows of `big` are shuffled, so every row group spans all dates.
#
# ✏️ **Exercise** · Write the same rows **sorted by `order_date`** to `OUT/lines_sorted.parquet` with
# `ROW_GROUP_SIZE 50000`. Then count, for both files, the row groups whose `order_date` range touches 2026-09-14.

# %%
# BEGIN SOLUTION
sorted_path = Q.posix(OUT / "lines_sorted.parquet")
con.execute(f"COPY (SELECT * FROM big ORDER BY order_date) TO '{sorted_path}' (FORMAT parquet, ROW_GROUP_SIZE 50000)")
# END SOLUTION

# %%
sorted_path = Q.posix(OUT / "lines_sorted.parquet")
if not (OUT / "lines_sorted.parquet").exists():  # safety net
    con.execute(f"COPY (SELECT * FROM big ORDER BY order_date) TO '{sorted_path}' (FORMAT parquet, ROW_GROUP_SIZE 50000)")


def groups_touching(path: str, day: str) -> tuple[int, int]:
    s = con.sql(f"""SELECT row_group_id, stats_min, stats_max FROM parquet_metadata('{path}')
                    WHERE path_in_schema = 'order_date'""").df()
    hit = s[(s.stats_min <= day) & (s.stats_max >= day)]
    return len(hit), len(s)


for name, path in [("shuffled", pq_path), ("sorted", sorted_path)]:
    hit, total = groups_touching(path, "2026-09-14")
    print(f"{name:9s} {hit} of {total} row groups may hold 2026-09-14")
hit_sorted, total_sorted = groups_touching(sorted_path, "2026-09-14")
Q.check(hit_sorted <= 2 < total_sorted, "sorted rows let a reader skip almost every row group")

# %% [markdown]
# ## 3 · Partition by month and query one month (8')
#
# ✏️ **Exercise** · Write `big` to `OUT/by_month/` partitioned by `month` (`PARTITION_BY (month)`), then define
# `one_month(src)` that returns revenue by category for confirmed lines of September from a source expression.
# Compare the partitioned folder with the single Parquet file: time, and bytes in the files the query needs.

# %%
part_dir = Q.posix(OUT / "by_month")
# BEGIN SOLUTION
con.execute(f"COPY big TO '{part_dir}' (FORMAT parquet, PARTITION_BY (month))")


def one_month(src: str):
    return con.execute(f"""SELECT category, round(sum(revenue)) FROM {src}
                           WHERE month = '2026-09' AND status = 'confirmed' GROUP BY 1 ORDER BY 1""").fetchall()
# END SOLUTION

# %%
try:
    one_month
except NameError:  # safety net
    con.execute(f"COPY big TO '{part_dir}' (FORMAT parquet, PARTITION_BY (month), OVERWRITE)")

    def one_month(src: str):
        return con.execute(f"SELECT category, round(sum(revenue)) FROM {src} WHERE month = '2026-09' AND status = 'confirmed' GROUP BY 1 ORDER BY 1").fetchall()
print(sorted(p.name for p in (OUT / "by_month").iterdir()))
t_single, a = Q.timed(lambda: one_month(f"read_parquet('{pq_path}')"))
t_part, b = Q.timed(lambda: one_month(f"read_parquet('{part_dir}/*/*.parquet', hive_partitioning = true)"))
print(f"single file: {round(1000 * t_single)} ms over {Q.mb(Q.folder_bytes(OUT / 'lines.parquet'))}")
print(f"partitioned: {round(1000 * t_part)} ms; the September folder holds {Q.mb(Q.folder_bytes(OUT / 'by_month' / 'month=2026-09'))}")
Q.check(a == b, "same answer from the single file and the partitions")

# %% [markdown]
# ## 4 · Too many small files, measured (5')
#
# Partitioning by a column with many values makes many small files. Each file has a footer to read and a request
# to make (on object storage, a request costs time and money).

# %%
tiny_dir = Q.posix(OUT / "by_day_customer")
con.execute(f"COPY big TO '{tiny_dir}' (FORMAT parquet, PARTITION_BY (order_date, customer_id))")
files = list((OUT / "by_day_customer").rglob("*.parquet"))
full = "SELECT round(sum(revenue)) FROM {src} WHERE status = 'confirmed'"
t_one, x = Q.timed(lambda: con.execute(full.format(src=f"read_parquet('{pq_path}')")).fetchall(), repeat=2)
t_many, y = Q.timed(lambda: con.execute(full.format(src=f"read_parquet('{tiny_dir}/*/*/*.parquet', hive_partitioning = true)")).fetchall(), repeat=2)
print(f"{len(files):,} files, median {Q.mb(sorted(f.stat().st_size for f in files)[len(files) // 2])}, together {Q.mb(Q.folder_bytes(OUT / 'by_day_customer'))}")
print(f"full scan: one file {round(1000 * t_one)} ms | {len(files):,} files {round(1000 * t_many)} ms")
Q.check(x == y and t_many > t_one, "same answer, slower from many small files")

# %% [markdown]
# 🔍 Rule of thumb from the Parquet documentation: row groups of hundreds of megabytes on large data, and files
# large enough that the footer is a small part of the read. Partition by a column that queries filter on and that
# has few values.

# %% [markdown]
# ## ✱ Stretch · Prove the pruning in the query plan

# %%
# BEGIN SOLUTION
plan = con.execute(f"""EXPLAIN ANALYZE SELECT count(*) FROM read_parquet('{part_dir}/*/*.parquet', hive_partitioning = true)
                       WHERE month = '2026-09'""").fetchall()
text = "\n".join(r[1] for r in plan)
print("\n".join(line for line in text.splitlines() if "File" in line or "Scanning" in line or "Filter" in line)[:1500])
# END SOLUTION

# %% [markdown]
# ## Checkpoint
#
# 1. A query on one month reads the whole folder. Name two causes.
#    <details><summary>Answer</summary>The files are not partitioned by month (or the filter is on another column),
#    or the filter wraps the partition column in an expression the reader cannot push down, such as
#    <code>strftime(order_date, ...)</code> instead of <code>month</code>.</details>
# 2. Why did sorting change how many row groups a reader skips?
#    <details><summary>Answer</summary>Sorted rows give each row group a narrow min-max range, so most ranges exclude
#    the filter value. Shuffled rows give every group the full range.</details>
# 3. Partition by `customer_id` too? When is that right?
#    <details><summary>Answer</summary>Rarely: 240 values times days makes thousands of tiny files. Only when most
#    queries filter on one customer and the data per customer is large.</details>
#
# **Carry forward.** Day 4 writes the margin mart as an open table partitioned by month: the same idea with a table
# format that records the partitions in metadata.
