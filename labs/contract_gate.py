"""Compile an ODCS data contract to SQL checks and run them in DuckDB (Labs 3.3 and 3.4, the capstone).

    import contract_gate as G
    contract = G.load(Path("contracts/supplier_prices.odcs.yaml"))
    results = G.run(con, contract, table="incoming")     # list of dicts: id, sql, value, passed, error

Supported: required properties (a missing column fails), and quality rules of the metrics nullValues,
duplicateValues, invalidValues (validValues), rowCount, and type sql with {object} and {property}. Operators:
mustBe, mustNotBe, mustBeGreaterThan, mustBeGreaterOrEqualTo, mustBeLessThan, mustBeLessOrEqualTo, mustBeBetween.
"""
from __future__ import annotations

from pathlib import Path

import yaml

OPS = {
    "mustBe": lambda v, t: v == t, "mustNotBe": lambda v, t: v != t,
    "mustBeGreaterThan": lambda v, t: v > t, "mustBeGreaterOrEqualTo": lambda v, t: v >= t,
    "mustBeLessThan": lambda v, t: v < t, "mustBeLessOrEqualTo": lambda v, t: v <= t,
    "mustBeBetween": lambda v, t: t[0] <= v <= t[1],
}
NUM_MACRO = ("CREATE OR REPLACE MACRO num(x) AS "
             "TRY_CAST(translate(CAST(x AS VARCHAR), '٠١٢٣٤٥٦٧٨٩٫,', '0123456789..') AS DOUBLE)")


def load(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def rule_sql(rule: dict, table: str, prop: str | None) -> str:
    if rule.get("type") == "sql":
        return rule["query"].replace("{object}", table).replace("{property}", prop or "")
    metric, args = rule["metric"], rule.get("arguments", {})
    if metric == "rowCount":
        return f"SELECT count(*) FROM {table}"
    if metric == "nullValues":
        return f"SELECT count(*) FROM {table} WHERE {prop} IS NULL"
    if metric == "duplicateValues":
        cols = ", ".join(args.get("properties", [prop]))
        return f"SELECT count(*) - count(DISTINCT ({cols})) FROM {table}"
    if metric == "invalidValues":
        values = ", ".join("'" + str(v).replace("'", "''") + "'" for v in args["validValues"])
        return f"SELECT count(*) FROM {table} WHERE {prop} IS NULL OR {prop} NOT IN ({values})"
    raise ValueError(f"metric {metric} is not supported")


def compile_contract(contract: dict, table: str) -> list[dict]:
    """One check per required property (the column exists) and one per quality rule."""
    checks = []
    for obj in contract["schema"]:
        for rule in obj.get("quality", []):
            checks.append({"id": rule["id"], "kind": "quality", "sql": rule_sql(rule, table, None), "rule": rule})
        for p in obj.get("properties", []):
            if p.get("required"):
                checks.append({"id": f"{p['name']}_present", "kind": "schema", "column": p["name"]})
            for rule in p.get("quality", []):
                checks.append({"id": rule["id"], "kind": "quality", "sql": rule_sql(rule, table, p["name"]), "rule": rule})
    return checks


def run(con, contract: dict, table: str) -> list[dict]:
    con.execute(NUM_MACRO)
    columns = {r[0] for r in con.execute(f"SELECT column_name FROM (DESCRIBE {table})").fetchall()}
    out = []
    for c in compile_contract(contract, table):
        if c["kind"] == "schema":
            ok = c["column"] in columns
            out.append({"id": c["id"], "sql": f"column {c['column']} exists", "value": ok, "passed": ok, "error": None})
            continue
        try:
            value = con.execute(c["sql"]).fetchall()[0][0]
            op = next(k for k in OPS if k in c["rule"])
            out.append({"id": c["id"], "sql": c["sql"], "value": value, "passed": bool(OPS[op](value, c["rule"][op])), "error": None})
        except Exception as e:  # noqa: BLE001 - a rule that cannot run is a failed rule
            out.append({"id": c["id"], "sql": c["sql"], "value": None, "passed": False, "error": str(e).splitlines()[0][:120]})
    return out
