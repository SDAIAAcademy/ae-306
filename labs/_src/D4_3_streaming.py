# %% [markdown]
# # Lab 4.3 · Shipment events with a watermark
#
# Day 4 · Session 3 (Streaming fundamentals) · 25 min. Qafila's carriers send shipment events (picked, departed,
# delivered) as they happen; some arrive hours or days late, some twice. Operations wants deliveries per day as the
# events come in, and finance wants them to agree with the batch figures. In this lab you consume the events from a
# local single-broker log by offset, survive a crash without double counting, count deliveries in daily event-time
# windows with a watermark, and reconcile with the batch result.
#
# **Reference state.** `data/raw/events/shipment_events.jsonl` (2,312 events for the last two weeks of October, in
# arrival order) and `extracts/shipments.jsonl` (the batch truth). `Q.Log` is a file-backed log with offsets and
# committed consumer positions, like one partition of a broker. Kafka is the production example on the slides.
#
# **Tasks**
# - [ ] 1 · Produce and consume by offset (5')
# - [ ] 2 · Crash, replay and count once (7')
# - [ ] 3 · Daily windows with a watermark (8')
# - [ ] 4 · Reconcile with the batch result (5')
# - [ ] ✱ Stretch · Two watermarks: what each one drops and how late it answers

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

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import pandas as pd

Q.ensure_data()
EVENTS = [json.loads(x) for x in (Q.RAW / "events" / "shipment_events.jsonl").read_text(encoding="utf-8").splitlines()]
WORK = Q.lab_dir("D4_3")
print(len(EVENTS), "events | first:", EVENTS[0]["event_id"], EVENTS[0]["status"], EVENTS[0]["event_time"])

# %% [markdown]
# ## 1 · Produce and consume by offset (5')
#
# A log is append-only: each record gets the next **offset**. A consumer reads from an offset and **commits** the
# offset it will read next, so after a restart it continues where it stopped.

# %%
log = Q.Log(WORK / "shipments")
for e in EVENTS:
    log.produce(e)
print("end offset:", log.end_offset)

# %% [markdown]
# ✏️ **Exercise** · Write `consume(log, group, handle, batch=100, crash_after=None)`: read from the committed offset
# of `group`, call `handle(record)` for each record, and commit after each batch. If `crash_after` is a number,
# raise `RuntimeError` after handling that many records **before** committing (a crash between processing and
# commit). Return the number of records handled.

# %%
def consume(log, group: str, handle, batch: int = 100, crash_after: int | None = None) -> int:
    # BEGIN SOLUTION
    handled = 0
    offset = log.committed(group)
    while offset < log.end_offset:
        records = log.read(offset, batch)
        for off, rec in records:
            handle(rec)
            handled += 1
            if crash_after is not None and handled >= crash_after:
                raise RuntimeError(f"consumer crashed at offset {off}, last commit {log.committed(group)}")
        offset = records[-1][0] + 1
        log.commit(group, offset)
    return handled
    # END SOLUTION


# %%
seen_statuses = Counter()
try:
    n = consume(log, "status-count", lambda r: seen_statuses.update([r["status"]]))
except NotImplementedError:  # safety net
    def consume(log, group, handle, batch=100, crash_after=None):
        handled, offset = 0, log.committed(group)
        while offset < log.end_offset:
            records = log.read(offset, batch)
            for off, rec in records:
                handle(rec); handled += 1
                if crash_after is not None and handled >= crash_after:
                    raise RuntimeError(f"consumer crashed at offset {off}, last commit {log.committed(group)}")
            offset = records[-1][0] + 1
            log.commit(group, offset)
        return handled
    n = consume(log, "status-count", lambda r: seen_statuses.update([r["status"]]))
print(n, "handled", dict(seen_statuses), "| committed:", log.committed("status-count"))
Q.check(n == len(EVENTS) and log.committed("status-count") == log.end_offset, "every event read once, offset committed at the end")
Q.check(consume(log, "status-count", print) == 0, "a restarted consumer resumes at its offset: nothing new to read")

# %% [markdown]
# ## 2 · Crash, replay and count once (7')
#
# The broker delivers **at least once**: after a crash between processing and commit, the consumer reads the batch
# again. Some events also arrive twice from the carrier. A counter that adds one per event counts them twice.
#
# ✏️ **Exercise** · Make the delivery count idempotent: `delivered` maps `shipment_id` to its delivery time, so a
# repeated event changes nothing. Run with a crash after 1,050 records, restart, and compare with the naive counter.

# %%
naive = Counter()
delivered: dict[str, str] = {}


def handle(rec: dict):
    if rec["status"] != "delivered":
        return
    naive[rec["event_time"][:10]] += 1
    # BEGIN SOLUTION
    delivered[rec["shipment_id"]] = rec["event_time"]
    # END SOLUTION


try:
    consume(log, "deliveries", handle, crash_after=1050)
except RuntimeError as e:
    print("crash:", e)
consume(log, "deliveries", handle)

# %%
if not delivered:  # safety net
    for e in EVENTS:
        if e["status"] == "delivered":
            delivered[e["shipment_id"]] = e["event_time"]
dup_events = len(EVENTS) - len({e["event_id"] for e in EVENTS})
print(f"naive count {sum(naive.values())} | idempotent count {len(delivered)} | duplicate events from carriers {dup_events}")
Q.check(sum(naive.values()) > len(delivered), "the naive counter double-counted the replayed and duplicated events")
Q.check(len(delivered) == len({e['shipment_id'] for e in EVENTS if e['status'] == 'delivered'}), "the idempotent count has each delivery once")

# %% [markdown]
# ## 3 · Daily windows with a watermark (8')
#
# Operations wants each day's deliveries as soon as the day is complete. Events carry two times: `event_time` (when
# the delivery happened) and `arrived_at` (when the event reached us). The **watermark** is the latest event time
# seen minus an allowed lateness: when it passes the end of a day, that day's window **closes** and its count is
# emitted. An event for a closed window is **late**: dropped from the emitted count and logged.
#
# ✏️ **Exercise** · Write `windowed(events, lateness)`: process events in arrival order; keep a set of shipment ids
# per open day (by `event_time[:10]`, delivered events only); close and emit every day whose end is at or before the
# watermark; count late deliveries (a repeat of a delivery already counted is a duplicate, not late). At the end of the input, emit the days still open. Return `(emitted, late)`, where
# `emitted` maps day to count.

# %%
def ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def windowed(events: list[dict], lateness: timedelta) -> tuple[dict, int]:
    # BEGIN SOLUTION
    open_days: dict[str, set] = defaultdict(set)
    emitted: dict[str, int] = {}
    counted, late_ids, max_event = set(), set(), None
    for e in events:
        if e["status"] != "delivered":
            continue
        t = ts(e["event_time"])
        day = e["event_time"][:10]
        if day in emitted:
            if e["shipment_id"] not in counted:      # a repeat of a counted delivery is not late, just a duplicate
                late_ids.add(e["shipment_id"])
            continue
        open_days[day].add(e["shipment_id"])
        max_event = t if max_event is None or t > max_event else max_event
        watermark = max_event - lateness
        for d in sorted(open_days):
            day_end = ts(d + "T00:00:00+03:00") + timedelta(days=1)
            if day_end <= watermark:
                ids = open_days.pop(d)
                emitted[d] = len(ids)
                counted |= ids
    for d in sorted(open_days):
        emitted[d] = len(open_days[d])
    return emitted, len(late_ids)
    # END SOLUTION


# %%
try:
    one_hour, late_1h = windowed(EVENTS, timedelta(hours=1))
except NotImplementedError:  # safety net: no watermark, count everything
    one_hour, late_1h = dict(Counter(e["event_time"][:10] for e in {e["event_id"]: e for e in EVENTS if e["status"] == "delivered"}.values())), 0
print("watermark 1 hour:", late_1h, "late events dropped")
print(one_hour)

# %% [markdown]
# ## 4 · Reconcile with the batch result (5')
#
# The batch truth: shipments shipped since 18 October and delivered before 1 November, counted per delivery day from
# `shipments.jsonl`.

# %%
ship = pd.read_json(Q.EXTRACTS / "shipments.jsonl", lines=True, dtype={"shipped_at": str, "delivered_at": str})
batch = ship[(ship.shipped_at.str[:10] >= "2026-10-18") & (ship.delivered_at < "2026-11-01")]
batch_days = batch.delivered_at.str[:10].value_counts().sort_index()
rec = pd.DataFrame({"batch": batch_days, "stream, 1 hour": pd.Series(one_hour)}).fillna(0).astype(int)
rec["missing"] = rec["batch"] - rec["stream, 1 hour"]
print(rec.to_string())
Q.check(rec.missing.sum() == late_1h and (rec.missing >= 0).all(), "every difference is a late event the watermark dropped")
idempotent_total = len({s for s, t in delivered.items() if t < "2026-11-01"})
Q.check(idempotent_total == rec.batch.sum(), "the stream without a watermark (all events, once) equals the batch")

# %% [markdown]
# 🔍 The stream is faster and, with a short watermark, incomplete. A daily batch recount repairs it: the usual
# design keeps both and reports the difference.

# %% [markdown]
# ## ✱ Stretch · Two watermarks
#
# Compare a 1-hour and a 1-day lateness: how many events each drops, and how long after a day ends its count is
# emitted (in event time).

# %%
# BEGIN SOLUTION
for lateness in (timedelta(hours=1), timedelta(days=1), timedelta(days=3)):
    em, late = windowed(EVENTS, lateness)
    diff = int(sum(abs(rec.batch.get(d, 0) - em.get(d, 0)) for d in rec.index))
    print(f"lateness {str(lateness):>16s}: {late:3d} late events dropped, {diff:3d} deliveries short of the batch, "
          f"each day emitted {lateness} after it ends")
# END SOLUTION

# %% [markdown]
# ## Checkpoint
#
# 1. A watermark of 1 hour against 1 day: what do you trade?
#    <details><summary>Answer</summary>Speed against completeness: 1 hour emits each day an hour after it ends and
#    drops more late events; 1 day waits a day and drops fewer.</details>
# 2. The consumer crashes after processing and before committing. What happens, and what makes it harmless?
#    <details><summary>Answer</summary>It reads the same records again (at-least-once). An idempotent update, keyed
#    by the shipment, makes the second read change nothing.</details>
# 3. Why window by event time and not by arrival time?
#    <details><summary>Answer</summary>Deliveries belong to the day they happened. By arrival time, a late event moves a
#    delivery to the wrong day and the stream never reconciles with the batch.</details>
#
# **Carry forward.** Nothing: the capstone is batch.
