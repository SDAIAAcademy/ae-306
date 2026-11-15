# %% [markdown]
# # Lab 4.4 · Classification, masking and access tests
#
# Day 4 · Session 4 (Governance with PDPL and NDMO) · 25 min. Qafila's customer and supplier tables hold people's
# names, phone numbers and e-mail addresses, bank accounts and contract terms. In this lab you classify every field
# under the four national classification levels, drop what the margin report does not need, give the analyst role
# (Dalia Sabri) a masked view, and **test** that the role cannot read customer contact data.
#
# **AI-tutor.** An AI assistant may give hints in this lab; it does not write your queries, models or tests.
#
# **Reference state.** `extracts/customers.csv` and `suppliers/suppliers_2026-10-31.csv` (the current tables),
# `customers_2026-09-30.csv` (last quarter's snapshot, before an erasure), and the star of Day 3
# (`Q.build_models`). All personal data in this course is synthetic. Nothing from another lab is needed.
#
# **Tasks**
# - [ ] 1 · The classification register (7')
# - [ ] 2 · Minimise: drop what the report does not need (4')
# - [ ] 3 · Masked views per role (7')
# - [ ] 4 · Access tests for the analyst role (7')
# - [ ] ✱ Stretch · Trace an erased customer through history and snapshots

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

import json
import re

import duckdb
import pandas as pd

WORK = Q.lab_dir("D4_4")
WAREHOUSE = WORK / "warehouse.duckdb"                  # every table: the data team's database
con = Q.warehouse(WAREHOUSE)
Q.build_models(con)
con.execute(f"CREATE OR REPLACE TABLE raw.customers AS SELECT * FROM read_csv('{Q.posix(Q.EXTRACTS)}/customers.csv', all_varchar = true)")
con.execute(f"CREATE OR REPLACE TABLE raw.suppliers AS SELECT * FROM read_csv('{Q.posix(Q.RAW)}/suppliers/suppliers_2026-10-31.csv', all_varchar = true)")
KEY = json.loads((Q.REF / "classification.json").read_text(encoding="utf-8"))
FIELDS = [f"customers.{c}" for c in con.table("raw.customers").columns] + [f"suppliers.{c}" for c in con.table("raw.suppliers").columns]
print(len(FIELDS), "fields to classify")
print(con.sql("SELECT * FROM raw.customers LIMIT 2"))

# %% [markdown]
# ## 1 · The classification register (7')
#
# The national Data Classification Policy (issued by the National Data Management Office, part of SDAIA) has four
# levels by the impact of unauthorised disclosure: **Top Secret** (high impact), **Secret** (medium),
# **Restricted** (low; older texts call this level Confidential), **Public** (none). Its examples of Restricted data include personally identifiable
# information such as names, phone numbers and bank account numbers, and supplier contracts and quotations; its
# examples of Public data include contact persons at organisations. Under the Personal Data Protection Law, a
# personal field also needs a purpose for each use.
#
# ✏️ **Exercise** · Fill `register`: for every field in `FIELDS`, `(level, is_personal, reason)`.

# %%
# BEGIN SOLUTION
register = {
    "customers.customer_id": ("Restricted", False, "links a customer to its detailed transactions"),
    "customers.name": ("Public", False, "the trading name on the shop's sign"),
    "customers.customer_type": ("Public", False, "a category, no impact"),
    "customers.city": ("Public", False, "a city, no impact"),
    "customers.contact_name": ("Restricted", True, "a person's name"),
    "customers.mobile": ("Restricted", True, "a person's phone number"),
    "customers.email": ("Restricted", True, "a person's e-mail address"),
    "customers.cr_number": ("Restricted", False, "a licence number tied to the credit file"),
    "customers.credit_limit_sar": ("Restricted", False, "the customer's financial standing"),
    "customers.created_at": ("Restricted", False, "internal account history"),
    "suppliers.supplier_id": ("Restricted", False, "links a supplier to its quotations"),
    "suppliers.name_en": ("Public", False, "a company name"),
    "suppliers.name_ar": ("Public", False, "a company name"),
    "suppliers.country": ("Public", False, "publicly known"),
    "suppliers.currency": ("Public", False, "publicly known"),
    "suppliers.payment_terms_days": ("Restricted", False, "a contract term"),
    "suppliers.contact_name": ("Restricted", True, "a person's name"),
    "suppliers.contact_email": ("Public", False, "the company's sales address"),
    "suppliers.iban": ("Restricted", False, "a bank account number"),
    "suppliers.contract_ref": ("Restricted", False, "identifies a supplier contract"),
}
# END SOLUTION

# %%
try:
    register
except NameError:  # safety net: the key
    register = {f: tuple(v) for f, v in KEY["key"].items()}
reg = pd.DataFrame([{"field": f, "level": v[0], "personal": v[1], "reason": v[2], "key level": KEY["key"][f][0],
                     "key personal": KEY["key"][f][1]} for f, v in register.items()])
print(reg[["field", "level", "personal", "key level"]].to_string(index=False))
Q.check(set(register) == set(FIELDS), "every field has a classification")
Q.check(all(v[0] in KEY["levels"] for v in register.values()), "every level is one of the four national levels")
personal_key = {f for f, v in KEY["key"].items() if v[1]}
Q.check({f for f, v in register.items() if v[1]} >= personal_key, "every personal field is marked personal")
Q.check(all(register[f][0] != "Public" for f in personal_key), "no personal field is Public")
print(f"agreement with the key: {(reg.level == reg['key level']).sum()} of {len(reg)} levels")
reg.to_csv(WORK / "classification_register.csv", index=False)

# %% [markdown]
# 🔍 `suppliers.contact_email` is the company's sales address: the policy's own example of Public data ("contact
# persons at organisations"). `suppliers.contact_name` is a person: Restricted. Where you differ from the key, your
# reason is what matters.

# %% [markdown]
# ## 2 · Minimise: drop what the report does not need (4')
#
# The margin mart answers finance's five questions with customer type and city. Nothing else about the customer.
#
# ✏️ **Exercise** · List in `needed` the customer fields the five questions need, and create `mart.dim_customer_min`
# with only those columns from `raw.customers` (plus the unknown member).

# %%
# BEGIN SOLUTION
needed = ["customer_id", "customer_type", "city"]
con.execute(f"""CREATE OR REPLACE TABLE mart.dim_customer_min AS
    SELECT {', '.join(needed)} FROM raw.customers UNION ALL SELECT 'Unknown', 'Unknown', 'Unknown'""")
# END SOLUTION

# %%
try:
    needed
except NameError:  # safety net
    needed = ["customer_id", "customer_type", "city"]
    con.execute("CREATE OR REPLACE TABLE mart.dim_customer_min AS SELECT customer_id, customer_type, city FROM raw.customers "
                "UNION ALL SELECT 'Unknown', 'Unknown', 'Unknown'")
dropped = [c for c in con.table("raw.customers").columns if c not in needed]
print("kept:", needed, "| dropped:", dropped)
Q.check(not set(needed) & {f.split(".")[1] for f in personal_key if f.startswith("customers.")}, "no personal field reaches the mart")

# %% [markdown]
# ## 3 · Masked views per role (7')
#
# Two roles read the data: the **finance controller** sees the customer table as it is (for credit control); the
# **analyst** sees a masked customer table and the minimised mart. DuckDB has no users or grants, so each role gets
# its **own database file** with only what it may read; in a warehouse the same design is a schema per role with
# `GRANT SELECT` on it.
#
# ✏️ **Exercise** · Write `build_analyst(path)`: a new DuckDB file attached as `analyst` containing
# `analyst.customers` with `contact_name` as initials, `mobile` with all but the last two digits hidden, `email`
# with the local part hidden, and no `cr_number` or `credit_limit_sar`; and `analyst.margin_lines`, the order-line
# fact joined to `mart.dim_customer_min` and the product category, without customer contact fields.

# %%
ANALYST_DB = WORK / "analyst.duckdb"


def build_analyst(path: Path):
    # BEGIN SOLUTION
    con.execute(f"ATTACH '{Q.posix(path)}' AS analyst")
    con.execute(r"""CREATE OR REPLACE TABLE analyst.customers AS
        SELECT customer_id, name, customer_type, city,
               regexp_replace(contact_name, '(\w)\w*', '\1.', 'g') AS contact_name,
               left(mobile, 4) || repeat('*', length(mobile) - 6) || right(mobile, 2) AS mobile,
               regexp_replace(email, '^[^@]+', '***') AS email
        FROM raw.customers""")
    con.execute("""CREATE OR REPLACE TABLE analyst.margin_lines AS
        SELECT f.order_id, f.line_no, f.order_date, c.customer_type, c.city, p.category,
               f.qty_pieces, f.revenue, f.cost, f.freight
        FROM mart.fct_order_line f JOIN mart.dim_customer_min c USING (customer_id) JOIN mart.dim_product p USING (product_id)""")
    con.execute("DETACH analyst")
    # END SOLUTION


# %%
try:
    build_analyst(ANALYST_DB)
except NotImplementedError:  # safety net
    con.execute(f"ATTACH '{Q.posix(ANALYST_DB)}' AS analyst")
    con.execute(r"""CREATE OR REPLACE TABLE analyst.customers AS SELECT customer_id, name, customer_type, city,
        regexp_replace(contact_name, '(\w)\w*', '\1.', 'g') AS contact_name, left(mobile, 4) || repeat('*', length(mobile) - 6) || right(mobile, 2) AS mobile,
        regexp_replace(email, '^[^@]+', '***') AS email FROM raw.customers""")
    con.execute("""CREATE OR REPLACE TABLE analyst.margin_lines AS SELECT f.order_id, f.line_no, f.order_date, c.customer_type, c.city,
        p.category, f.qty_pieces, f.revenue, f.cost, f.freight FROM mart.fct_order_line f JOIN mart.dim_customer_min c USING (customer_id)
        JOIN mart.dim_product p USING (product_id)""")
    con.execute("DETACH analyst")
con.close()


def connect_as(role: str):
    """The analyst gets her own file, read only; the finance controller gets the warehouse, read only."""
    return duckdb.connect(str(ANALYST_DB if role == "analyst" else WAREHOUSE), read_only=True)


dalia = connect_as("analyst")
print(dalia.sql("SELECT * FROM customers LIMIT 3"))

# %% [markdown]
# ## 4 · Access tests for the analyst role (7')
#
# A rule nobody tests is a wish. Write tests that fail the build if the analyst can read what she must not.
#
# ✏️ **Exercise** · Fill `ACCESS_TESTS`: each a function of a connection that returns `True` when the rule holds:
# (1) the raw customer table cannot be read; (2) no value of any analyst table looks like a full Saudi mobile number
# (`+9665` and 8 digits); (3) no value contains a full e-mail address; (4) the analyst can still answer finance's
# question 5 (margin by city).

# %%
PHONE = re.compile(r"\+9665\d{8}")
EMAIL = re.compile(r"[A-Za-z0-9._-]+@[A-Za-z0-9.-]+")


def all_values(c) -> list[str]:
    out = []
    for s, t in c.execute("SELECT table_schema, table_name FROM information_schema.tables").fetchall():
        for row in c.execute(f"SELECT * FROM {s}.{t}").fetchall():
            out += [str(v) for v in row if v is not None]
    return out


# BEGIN SOLUTION
def cannot_read_raw(c) -> bool:
    try:
        c.execute("SELECT * FROM raw.customers LIMIT 1").fetchall()
        return False
    except duckdb.Error:
        return True


ACCESS_TESTS = {
    "raw customer table not readable": cannot_read_raw,
    "no full mobile number": lambda c: not any(PHONE.search(v) for v in all_values(c)),
    "no full e-mail address": lambda c: not any(EMAIL.search(v) and not v.startswith("***") for v in all_values(c)),
    "margin by city still answerable": lambda c: len(c.execute(
        "SELECT city, sum(revenue) - sum(cost) FROM margin_lines GROUP BY 1").fetchall()) == 4,
}
# END SOLUTION

# %%
try:
    ACCESS_TESTS
except NameError:  # safety net
    ACCESS_TESTS = {"no full mobile number": lambda c: not any(PHONE.search(v) for v in all_values(c))}
results = {name: test(dalia) for name, test in ACCESS_TESTS.items()}
for name, ok in results.items():
    print(("PASS " if ok else "FAIL ") + name)
finance = connect_as("finance")
print("the same tests on the finance controller's connection:", {n: t(finance) for n, t in list(ACCESS_TESTS.items())[:2]})
Q.check(all(results.values()) and len(results) >= 4, "the analyst role passes every access test")
q5 = {r["city"]: r["margin"] for r in Q.reference("finance_answers")["q5_city_after_freight"]}
mine = dict(dalia.execute("SELECT city, round(sum(revenue) - sum(cost), 2) FROM margin_lines GROUP BY 1").fetchall())
Q.check(all(abs(float(mine[c]) - q5[c]) < 1 for c in q5), "masking cost the analyst nothing: question 5 still matches finance")

# %% [markdown]
# 🔍 The tests fail on the finance controller's connection, as they should: the rules belong to the role.

# %% [markdown]
# ## ✱ Stretch · Trace an erased customer
#
# Customer C-1187 asked to be erased. The current customer table no longer has the row. Where else is the person?

# %%
# BEGIN SOLUTION
hits = []
for p in sorted(Q.RAW.rglob("*")):
    if p.is_file() and p.suffix in (".csv", ".jsonl"):
        text = p.read_text(encoding="utf-8")
        if "C-1187" in text:
            line = next(x for x in text.splitlines() if "C-1187" in x)
            hits.append({"file": p.relative_to(Q.LABS).as_posix(), "personal data on the line": bool(PHONE.search(line) or EMAIL.search(line))})
print(pd.DataFrame(hits).to_string(index=False))
print("orders kept with the unknown member:", finance.execute("SELECT count(DISTINCT order_id) FROM mart.fct_order_line WHERE customer_id = 'Unknown'").fetchall()[0][0])
print("Last quarter's snapshot still holds the contact: erasure must reach snapshots, backups and every table version"
      " (Iceberg snapshots included, by expiring them), not only the current table.")
# END SOLUTION
dalia.close()
finance.close()

# %% [markdown]
# ## Checkpoint
#
# 1. A deleted customer still shows in last month's snapshot. What removes it?
#    <details><summary>Answer</summary>Erasure applied to every copy: rewrite or delete the snapshot file, expire the
#    table versions that hold it, and record that it was done. Deleting the current row is not enough.</details>
# 2. Why minimise before masking?
#    <details><summary>Answer</summary>A field that is not there cannot leak and needs no mask, no test and no purpose.
#    Masking is for fields a role needs in part.</details>
# 3. What does an access test prove that a policy document does not?
#    <details><summary>Answer</summary>That the rule holds in the system today, on every build: a change that exposes
#    a phone number fails the pipeline instead of reaching the analyst.</details>
#
# **Carry forward.** The capstone's README includes this register and these tests.
