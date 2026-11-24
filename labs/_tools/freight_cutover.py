"""Numbers of the slide `cutover-register` (Day 3, session 3): a rename done in parallel, on the shipment extract.

    cd labs
    uv run python _tools/freight_cutover.py

The scenario: the shipment extract renames `freight_sar` to `freight_cost`. In the expand phase the producer writes
both fields in every row. This script replays the last 14 days of shipments in the data as those two-field rows,
runs the parallel check (rows where the two fields disagree) and prints the cutover decision for the register of
consumers shown on the slide. Every number on the slide comes from this output.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

LABS = Path(__file__).resolve().parents[1]
SHIPMENTS = LABS / "data" / "raw" / "extracts" / "shipments.jsonl"
WINDOW_DAYS = 14

# Which field each consumer of the shipment extract reads today (the register on the slide).
CONSUMERS = {
    "fct_order_line (freight allocation)": "freight_cost",
    "carrier cost review": "freight_cost",
    "monthly freight file for finance": "freight_sar",
}


def main() -> None:
    rows = [json.loads(line) for line in SHIPMENTS.read_text(encoding="utf-8").splitlines() if line.strip()]
    last = max(date.fromisoformat(r["shipped_at"][:10]) for r in rows)
    first = last - timedelta(days=WINDOW_DAYS - 1)
    window = [r for r in rows if first <= date.fromisoformat(r["shipped_at"][:10]) <= last]
    # The expand phase: the producer writes the same value under both names.
    dual = [{**r, "freight_cost": round(float(r["freight_sar"]), 2)} for r in window]
    mismatches = sum(1 for r in dual if round(float(r["freight_sar"]), 2) != r["freight_cost"])
    still_old = [name for name, field in CONSUMERS.items() if field == "freight_sar"]
    can_drop = mismatches == 0 and not still_old

    print(f"window: {first} to {last} ({WINDOW_DAYS} days)")
    print(f"two-field rows checked: {len(dual):,}")
    print(f"rows where freight_sar and freight_cost disagree: {mismatches}")
    for name, field in CONSUMERS.items():
        print(f"  {name:38s} reads {field}")
    print(f"consumers still on freight_sar: {len(still_old)} ({', '.join(still_old) or 'none'})")
    print(f"can 2.0.0 drop freight_sar today? {'yes' if can_drop else 'no'}")


if __name__ == "__main__":
    main()
