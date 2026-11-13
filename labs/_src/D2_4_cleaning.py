# %% [markdown]
# # Lab 2.4 · Currencies, units and Arabic names
#
# Day 2 · Session 4 (Cleaning with dataframes) · 25 min. The supplier prices arrive as text: some costs in
# Arabic-Indic digits (`٣٫٣٣`), some with a decimal comma (`36,09`), in SAR, USD or AED, per carton or per piece,
# and the supplier's Arabic name spelt several ways by different clerks. Finance needs one cost per piece in SAR and
# one supplier id. In this lab you write the cleaning rules as Polars expressions, log what each rule changed, and
# reconcile the result with the ERP's price list.
#
# **Reference state.** `data/raw/supplier_api/price_records.jsonl` (every version the API served),
# `extracts/products.csv` (units per carton, supplier per product), `suppliers/*.csv` (the supplier names) and
# `extracts/prices.csv` (the ERP's cost per piece, for the reconciliation). Nothing from another lab is needed.
#
# **Tasks**
# - [ ] 1 · Profile the raw prices (4')
# - [ ] 2 · Digits and currencies (6')
# - [ ] 3 · Units: cartons to pieces (5')
# - [ ] 4 · Arabic supplier names to one id (6')
# - [ ] 5 · The rule log and the reconciliation (4')
# - [ ] ✱ Stretch · The same rules as a lazy plan: read the optimised plan

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
import polars as pl

pl.Config.set_tbl_rows(12)
pl.Config.set_fmt_str_lengths(40)
print("polars", pl.__version__)

raw = (pl.read_ndjson(Q.RAW / "supplier_api" / "price_records.jsonl")
       .sort("updated_at").unique("price_id", keep="last").sort("price_id"))   # latest version of each price
products = pl.read_csv(Q.EXTRACTS / "products.csv")
print(raw.shape, "latest versions")

# %% [markdown]
# ## 1 · Profile the raw prices (4')

# %%
print(raw.group_by("currency", "unit").len().sort("currency", "unit"))
not_plain = raw.filter(~pl.col("cost").str.contains(r"^\d+\.\d+$"))
print(len(not_plain), "costs are not plain decimals:", not_plain["cost"].head(6).to_list())
print(raw["supplier_name"].n_unique(), "spellings of", products["supplier_id"].n_unique(), "suppliers")

# %% [markdown]
# 🔍 Three currencies, two units, two non-standard number formats and three times as many name spellings as
# suppliers. Every rule below must say how many rows it changed: that log is what lets Lujain trust the result.

# %% [markdown]
# ## 2 · Digits and currencies (6')
#
# A rule is a name and a Polars expression. `apply(df, rules)` (given) runs them in order and logs, per rule, how
# many rows it changed.
#
# ✏️ **Exercise** · Write two rules:
# - `digits`: `cost_text` with Arabic-Indic digits and the Arabic decimal separator `٫` turned into `0-9` and `.`,
#   and a decimal comma turned into a point;
# - `to_sar`: `cost_sar`, the cost as a number times the rate of its currency (`Q.RATES`: SAR 1, USD 3.75,
#   AED 1.0211).

# %%
log: list[dict] = []


def apply(df: pl.DataFrame, rules: list[tuple[str, str, pl.Expr]]) -> pl.DataFrame:
    """Each rule writes one column. The log counts rows whose value differs from the column it replaced."""
    for name, column, expr in rules:
        before = df[column] if column in df.columns else None
        df = df.with_columns(expr.alias(column))
        changed = len(df) if before is None else int((df[column].cast(pl.String) != before.cast(pl.String)).fill_null(True).sum())
        log.append({"rule": name, "column": column, "rows_changed": changed})
    return df


AR_DIGITS = "٠١٢٣٤٥٦٧٨٩٫"
EN_DIGITS = "0123456789."
# BEGIN SOLUTION
NUMBER_RULES = [
    ("digits", "cost_text", pl.col("cost").str.strip_chars()
        .str.replace_many(list(AR_DIGITS), list(EN_DIGITS)).str.replace(",", ".", literal=True)),
    ("to_sar", "cost_sar", pl.col("cost_text").cast(pl.Float64) * pl.col("currency").replace_strict(Q.RATES, return_dtype=pl.Float64)),
]
# END SOLUTION

# %%
try:
    NUMBER_RULES
except NameError:  # safety net
    NUMBER_RULES = [("digits", "cost_text", pl.col("cost").str.strip_chars().str.replace_many(list(AR_DIGITS), list(EN_DIGITS))
                     .str.replace(",", ".", literal=True)),
                    ("to_sar", "cost_sar", pl.col("cost_text").cast(pl.Float64) * pl.col("currency").replace_strict(Q.RATES, return_dtype=pl.Float64))]
df = raw.with_columns(pl.col("cost").alias("cost_text"))
df = apply(df, NUMBER_RULES)
print(df.select("price_id", "cost", "cost_text", "currency", "cost_sar").filter(pl.col("cost") != pl.col("cost_text")).head(5))
Q.check(df["cost_sar"].null_count() == 0 and (df["cost_sar"] > 0).all(), "every cost is a positive number in SAR")

# %% [markdown]
# ## 3 · Units: cartons to pieces (5')
#
# ✏️ **Exercise** · Join `units_per_carton` from `products` and write the rule `per_piece`: `cost_piece_sar`, the
# SAR cost divided by the units per carton when `unit` is `carton`, rounded to 2 decimals **once, at the end**.

# %%
df = df.join(products.select("product_id", "units_per_carton", pl.col("supplier_id").alias("product_supplier")),
             on="product_id", how="left")
# BEGIN SOLUTION
UNIT_RULES = [("per_piece", "cost_piece_sar",
               (pl.when(pl.col("unit") == "carton").then(pl.col("cost_sar") / pl.col("units_per_carton"))
                .otherwise(pl.col("cost_sar"))).round(2))]
# END SOLUTION

# %%
try:
    UNIT_RULES
except NameError:  # safety net
    UNIT_RULES = [("per_piece", "cost_piece_sar", (pl.when(pl.col("unit") == "carton").then(pl.col("cost_sar") / pl.col("units_per_carton"))
                                                   .otherwise(pl.col("cost_sar"))).round(2))]
df = apply(df, UNIT_RULES)
Q.check(df["units_per_carton"].null_count() == 0, "every price found its product")
print(df.select("product_id", "currency", "unit", "cost_text", "units_per_carton", "cost_piece_sar").head(5))

# %% [markdown]
# ## 4 · Arabic supplier names to one id (6')
#
# The clerks' spellings differ by: spaces around the name, a company prefix (`شركة`, `مؤسسة`), the tatweel
# stretching character (`ـ`), hamza forms of alef (`أ` `إ` `آ` against `ا`) and taa marbuta (`ة` against `ه`).
# Normalise both sides the same way, then join.
#
# ✏️ **Exercise** · Write `normalise(expr)` returning a Polars expression that applies those five rules, and the
# rule `supplier_id` that maps each record's normalised name to the id of the supplier with the same normalised
# `name_ar` (`names`, given).

# %%
def normalise(e: pl.Expr) -> pl.Expr:
    # BEGIN SOLUTION
    return (e.str.strip_chars()
             .str.replace(r"^(شركة|مؤسسة)\s+", "")
             .str.replace_all("ـ", "", literal=True)
             .str.replace_all(r"[أإآ]", "ا")
             .str.replace_all("ة", "ه", literal=True)
             .str.replace_all(r"\s+", " "))
    # END SOLUTION


# %%
suppliers = pl.concat([pl.read_csv(Q.RAW / "suppliers" / "suppliers_2026-08-01.csv"),
                       pl.read_csv(Q.RAW / "suppliers" / "suppliers_2026-10-31.csv")]).unique("supplier_id")
try:
    names = suppliers.select(normalise(pl.col("name_ar")).alias("name_key"), "supplier_id")
except NotImplementedError:  # safety net
    def normalise(e):
        return (e.str.strip_chars().str.replace(r"^(شركة|مؤسسة)\s+", "").str.replace_all("ـ", "", literal=True)
                 .str.replace_all(r"[أإآ]", "ا").str.replace_all("ة", "ه", literal=True).str.replace_all(r"\s+", " "))
    names = suppliers.select(normalise(pl.col("name_ar")).alias("name_key"), "supplier_id")
df = apply(df, [("name_key", "name_key", normalise(pl.col("supplier_name")))])
df = df.join(names, on="name_key", how="left")
log.append({"rule": "supplier_id", "column": "supplier_id", "rows_changed": int(df["supplier_id"].is_not_null().sum())})
print(df["supplier_name"].n_unique(), "spellings ->", df["name_key"].n_unique(), "names ->", df["supplier_id"].n_unique(), "ids")
Q.check(df["supplier_id"].null_count() == 0, "every spelling maps to a supplier")
Q.check((df["supplier_id"] == df["product_supplier"]).all(), "and to the supplier the product belongs to")

# %% [markdown]
# ## 5 · The rule log and the reconciliation (4')
#
# The ERP's price list holds the cost per piece in SAR that procurement keyed in by hand. Every one of the 102
# latest prices should match it.

# %%
rule_log = pl.DataFrame(log)
print(rule_log)
erp = pl.read_csv(Q.EXTRACTS / "prices.csv", try_parse_dates=True).with_columns(pl.col("valid_from").cast(pl.String))
rec = df.join(erp.select("product_id", "valid_from", pl.col("cost_piece_sar").alias("erp_cost")), on=["product_id", "valid_from"], how="full",
              coalesce=True)
rec = rec.with_columns((pl.col("cost_piece_sar") - pl.col("erp_cost")).abs().alias("diff"))
print(rec.select(pl.len().alias("rows"), pl.col("cost_piece_sar").null_count().alias("only_in_erp"),
                 pl.col("erp_cost").null_count().alias("only_in_api"), (pl.col("diff") > 0.011).sum().alias("differ"), (pl.col("diff") > 0.005).sum().alias("one_halala")))
Q.check(len(rec) == 102 and rec["diff"].max() <= 0.011, "102 prices: the cleaned API equals the ERP within one halala of rounding")
Q.ensure_data()
clean = df.select("price_id", "product_id", "supplier_id", "valid_from", "cost_piece_sar", "updated_at")
clean.write_parquet(Q.lab_dir("D2_4") / "supplier_prices_clean.parquet")

# %% [markdown]
# 🔍 Change one rule (round before dividing by the units, or forget the decimal comma) and run the last two cells
# again: the reconciliation shows exactly which prices move.

# %% [markdown]
# ## ✱ Stretch · The same rules as a lazy plan
#
# `pl.scan_ndjson` builds a plan instead of reading the file. Polars optimises the whole plan before it runs:
# read the optimised plan and find the projection pushdown (only the columns the result needs are read).

# %%
# BEGIN SOLUTION
plan = (pl.scan_ndjson(Q.RAW / "supplier_api" / "price_records.jsonl")
        .with_columns(NUMBER_RULES[0][2].alias("cost_text"))
        .with_columns(NUMBER_RULES[1][2].alias("cost_sar"))
        .filter(pl.col("currency") == "USD")
        .select("price_id", "cost_sar"))
print(plan.explain())
print(plan.collect().head(3))
# END SOLUTION

# %% [markdown]
# ## Checkpoint
#
# 1. Convert the currency then the unit, or the unit then the currency?
#    <details><summary>Answer</summary>Either: both are multiplications. What matters is rounding once, at the end;
#    rounding between the steps moves the cost per piece by up to half a halala per carton unit.</details>
# 2. Why keep the rules as data (a list of name and expression) rather than one long chain?
#    <details><summary>Answer</summary>Each rule can be logged, tested and reviewed on its own, and the log says how
#    many rows each one changed, which is the evidence that the cleaning did what it claims.</details>
# 3. A new spelling arrives that does not map. What should the pipeline do?
#    <details><summary>Answer</summary>Stop or quarantine the row and report it (Day 3's contract), never guess an id:
#    a wrong supplier moves margin between suppliers silently.</details>
#
# **Carry forward.** `artifacts/D2_4/supplier_prices_clean.parquet`; Day 3 starts from the ERP list, which these
# prices now reconcile with.
