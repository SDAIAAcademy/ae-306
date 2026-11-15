"""Qafila Trading: the synthetic data of the course, and its answer key.

    uv run python qafila_data.py          # writes data/raw/ and data/reference/ (a few seconds)
    uv run python qafila_data.py --force  # writes them again

Standard library only, seed 306: every run writes the same data. August to October 2026.
Nothing here is real: organisations, people, numbers, phone numbers and addresses are invented.
The planted problems are listed in PLANTED below and, with the numbers, in solutions/answer_key.md.
"""
from __future__ import annotations

import csv
import json
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

LABS = Path(__file__).resolve().parent
RAW = LABS / "data" / "raw"
REF = LABS / "data" / "reference"
SEED = 306
START, END = date(2026, 8, 1), date(2026, 10, 31)
RIYADH = timezone(timedelta(hours=3))
RATES = {"SAR": 1.0, "USD": 3.75, "AED": 1.0211}          # SAR per unit of currency (fixed for the course)
API_SPLIT = datetime(2026, 10, 16, tzinfo=RIYADH)          # first release of the API ends here
INCOTERM_FROM = datetime(2026, 10, 1, tzinfo=RIYADH)       # the API adds "incoterm" from here
DUP_DAY = date(2026, 9, 14)                                # the extract re-sent this day's order lines
ERASED = "C-1187"                                          # erasure request: removed from the customer table
STREAM_FROM = date(2026, 10, 18)                           # shipment events cover the last two weeks

PLANTED = """
1. order_lines.csv repeats every line of the orders placed on 2026-09-14 (a re-sent batch). Lab 1.2.
2. The old margin report counts cancelled orders. Lab 1.2.
3. Order lines are priced per carton or per piece; cost is per piece. Lab 1.2.
4. Prices change inside the quarter: cost needs the price valid on the order date. Labs 1.2, 1.3.
5. Customer C-1187 asked to be erased: the customer row is gone, the orders stay (orphans). Labs 3.1, 4.4.
6. The supplier API re-sends corrected prices with a later updated_at, and adds "incoterm" in October. Labs 2.1, 2.2.
7. API costs come per carton or per piece, in SAR, USD or AED, some with Arabic-Indic digits or a decimal comma,
   and supplier names in several Arabic spellings. Lab 2.4.
8. The supplier change feed repeats three events and delivers two out of order. Lab 2.3.
9. Supplier S-07 moves from the UAE to Saudi Arabia on 2026-09-01; S-12 is deleted on 2026-10-10. Labs 2.3, 3.1.
10. Freight is per shipment (one per order): joining it to lines repeats it. Lab 3.1.
11. The November supplier batch renames "cost" to "unit_cost" and carries a negative cost. Labs 3.3, 3.4.
12. Shipment events arrive late (some by days) and some twice. Lab 4.3.
"""

CITIES = [("Jeddah", "جدة", .45), ("Riyadh", "الرياض", .35), ("Dammam", "الدمام", .20)]
TYPES = [("shop", .50), ("restaurant", .25), ("caterer", .15), ("hotel", .10)]
SHOP_WORDS = {"shop": ["Mini Market", "Grocery", "Store"], "restaurant": ["Restaurant", "Kitchen", "Grill"],
              "caterer": ["Catering", "Events Kitchen"], "hotel": ["Hotel", "Suites"]}
NAME_WORDS = ["Al Noor", "Al Rawdah", "Al Safa", "Durrat", "Al Bustan", "Al Manar", "Lulu", "Al Waha Corner",
              "Sanabel", "Al Hamra", "Najmat", "Al Faisaliah", "Al Andalus", "Taiba", "Al Shati", "Rimal"]
FIRST = ["Abdulrahman", "Nawaf", "Saleh", "Majid", "Ziyad", "Waleed", "Mishal", "Hatem", "Reem", "Shahad", "Lama",
         "Asma", "Wafa", "Nouf", "Arwa", "Hind"]
FAMILY = ["Al-Rashid", "Al-Shehri", "Al-Ghamdi", "Al-Dosari", "Al-Qarni", "Al-Juhani", "Al-Anazi", "Al-Shammari",
          "Al-Otaibi", "Al-Balawi", "Al-Maliki", "Al-Yami"]
CATEGORIES = {
    "Rice and grains": ["Basmati rice 5 kg", "Sella rice 10 kg", "Bulgur 1 kg", "Red lentils 1 kg", "Chickpeas 1 kg"],
    "Oils and ghee": ["Sunflower oil 1.8 l", "Corn oil 1.5 l", "Olive oil 1 l", "Ghee 800 g"],
    "Canned food": ["Tuna 160 g", "Fava beans 400 g", "Tomato paste 400 g", "Sweet corn 340 g", "Chickpea hummus 380 g"],
    "Beverages": ["Mineral water 330 ml", "Mango juice 1 l", "Arabic coffee 500 g", "Black tea 100 bags", "Laban 1 l"],
    "Cleaning": ["Dish soap 1 l", "Laundry powder 3 kg", "Bleach 2 l", "Floor cleaner 3 l"],
    "Paper and packaging": ["Paper towels 6 rolls", "Takeaway boxes 50", "Aluminium foil 30 m", "Napkins 500"],
}
# id, English name, Arabic name, country, currency
SUPPLIERS = [
    ("S-01", "Al Amana Foods", "الأمانة للأغذية", "SA", "SAR"), ("S-02", "Hijaz Grains", "حبوب الحجاز", "SA", "SAR"),
    ("S-03", "Sahil Oils", "زيوت الساحل", "SA", "SAR"), ("S-04", "Najd Dairy", "ألبان نجد", "SA", "SAR"),
    ("S-05", "Bayader Paper", "بيادر للورق", "SA", "SAR"), ("S-06", "Khaleej Trading", "الخليج التجارية", "AE", "AED"),
    ("S-07", "Jumeirah Canning", "جميرا للمعلبات", "AE", "AED"), ("S-08", "Emirates Clean", "الإمارات للمنظفات", "AE", "AED"),
    ("S-09", "Nile Valley Foods", "وادي النيل للأغذية", "EG", "USD"), ("S-10", "Delta Beans", "فول الدلتا", "EG", "USD"),
    ("S-11", "Anatolia Pantry", "مؤونة الأناضول", "TR", "USD"), ("S-12", "Bosphorus Oils", "زيوت البوسفور", "TR", "USD"),
    ("S-13", "Izmir Packaging", "إزمير للتغليف", "TR", "USD"), ("S-14", "Kerala Spice Rice", "أرز كيرلا", "IN", "USD"),
    ("S-15", "Punjab Basmati", "بسمتي البنجاب", "IN", "USD"), ("S-16", "Deccan Tea", "شاي الدكن", "IN", "USD"),
    ("S-17", "Tihama Water", "مياه تهامة", "SA", "SAR"), ("S-18", "Asir Coffee", "قهوة عسير", "SA", "SAR"),
]
NEW_SUPPLIERS = [("S-19", "Qassim Dates", "تمور القصيم", "SA", "SAR", date(2026, 9, 10)),
                 ("S-20", "Muscat Foods", "مسقط للأغذية", "OM", "USD", date(2026, 10, 5))]
CATEGORY_SUPPLIERS = {"Rice and grains": ["S-02", "S-14", "S-15", "S-10"], "Oils and ghee": ["S-03", "S-12", "S-11"],
                      "Canned food": ["S-01", "S-07", "S-09", "S-10"], "Beverages": ["S-04", "S-16", "S-17", "S-18", "S-06"],
                      "Cleaning": ["S-08", "S-06"], "Paper and packaging": ["S-05", "S-13"]}
CARRIERS = ["Naql Express", "Bahr Freight", "Qafila fleet"]
ARABIC_DIGITS = str.maketrans("0123456789.", "٠١٢٣٤٥٦٧٨٩٫")


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def weighted(rng, pairs):
    x, acc = rng.random() * sum(w for *_, w in pairs), 0.0
    for p in pairs:
        acc += p[-1]
        if x <= acc:
            return p
    return pairs[-1]


def ar_variant(rng, name: str, i: int) -> str:
    """One of several spellings of an Arabic supplier name, as different clerks type it."""
    forms = [name, "شركة " + name, "مؤسسة " + name, name.replace("أ", "ا").replace("إ", "ا"),
             name.replace("ة", "ه"), name.replace("ا", "ـا", 1), "  " + name + " "]
    return forms[i % len(forms)]


# ------------------------------------------------------------------------------------------------ generators
def make_customers(rng):
    rows = []
    for n in range(240):
        cid = f"C-{1001 + n}"
        kind = weighted(rng, TYPES)[0]
        city, city_ar, _ = weighted(rng, CITIES)
        first, fam = rng.choice(FIRST), rng.choice(FAMILY)
        rows.append({
            "customer_id": cid, "name": f"{rng.choice(NAME_WORDS)} {rng.choice(SHOP_WORDS[kind])} {n % 37 + 1}",
            "customer_type": kind, "city": city, "contact_name": f"{first} {fam}",
            "mobile": f"+9665{rng.randint(0, 99999999):08d}",
            "email": f"{first.lower()}.{fam.lower().replace('al-', '')}{n}@{city.lower()}-shop.example",
            "cr_number": f"{ {'Jeddah': 4030, 'Riyadh': 1010, 'Dammam': 2050}[city]}{rng.randint(0, 999999):06d}",
            "credit_limit_sar": rng.choice([20000, 50000, 100000, 250000]),
            "created_at": (date(2024, 1, 1) + timedelta(days=rng.randint(0, 900))).isoformat(),
        })
    return rows


def make_suppliers(rng):
    rows = []
    for sid, en, ar, country, ccy in SUPPLIERS:
        rows.append({"supplier_id": sid, "name_en": en, "name_ar": ar, "country": country, "currency": ccy,
                     "payment_terms_days": rng.choice([30, 45, 60, 90]),
                     "contact_name": f"{rng.choice(FIRST)} {rng.choice(FAMILY)}",
                     "contact_email": f"sales@{en.lower().replace(' ', '-')}.example",
                     "iban": f"{ 'SA' if country == 'SA' else country}{rng.randint(10, 99)}{rng.randint(0, 10**18 - 1):018d}",
                     "contract_ref": f"QT-CON-{2025 if rng.random() < .6 else 2026}-{int(sid[2:]):03d}"})
    return rows


def make_products(rng):
    rows, n = [], 0
    for cat, items in CATEGORIES.items():
        for item in items:
            for sid in CATEGORY_SUPPLIERS[cat]:
                if rng.random() < .55 or len([r for r in rows if r["category"] == cat]) < 2:
                    n += 1
                    units = rng.choice([6, 12, 24])
                    price = round(rng.uniform(3, 60), 2)
                    rows.append({"product_id": f"P-{1000 + n}", "name": item, "category": cat, "supplier_id": sid,
                                 "units_per_carton": units, "list_price_piece_sar": price})
    return rows


def make_prices(rng, products, suppliers):
    """Supplier API price records: one per price version, 25 of them corrected later."""
    ccy = {s["supplier_id"]: s["currency"] for s in suppliers}
    ar = {s["supplier_id"]: s["name_ar"] for s in suppliers}
    api, k = [], 0
    for p in products:
        base = p["list_price_piece_sar"] * rng.uniform(.68, .84)
        starts = [date(2026, 7, 1)]
        if rng.random() < .5:
            starts.append(date(2026, 8, 15) + timedelta(days=rng.randint(0, 60)))
            if rng.random() < .3:
                starts.append(starts[-1] + timedelta(days=rng.randint(10, 20)))
        sid, c = p["supplier_id"], ccy[p["supplier_id"]]
        unit = "carton" if rng.random() < .7 else "piece"
        for j, vf in enumerate(starts):
            k += 1
            cost_piece_sar = base * (1 + (rng.uniform(-.05, .12) if j else 0))
            per = p["units_per_carton"] if unit == "carton" else 1
            cost_ccy = round(cost_piece_sar * per / RATES[c], 2)
            upd = datetime(vf.year, vf.month, vf.day, 6, 0, tzinfo=RIYADH) - timedelta(days=rng.randint(1, 6),
                                                                                        minutes=rng.randint(0, 600))
            api.append({"price_id": f"PR-{k:05d}", "product_id": p["product_id"], "supplier_id": sid,
                        "supplier_name": ar_variant(rng, ar[sid], k), "cost": cost_ccy, "currency": c, "unit": unit,
                        "valid_from": vf.isoformat(), "updated_at": upd})
    # corrections: 25 records re-sent late in October with a corrected cost
    for rec in rng.sample(api, 25):
        rec["cost"] = round(rec["cost"] * rng.choice([.97, 1.03, 1.05]), 2)
        rec["corrected_at"] = datetime(2026, 10, rng.randint(17, 30), rng.randint(7, 20), tzinfo=RIYADH)
    return api


def text_cost(rng, rec) -> str:
    s = f"{rec['cost']:.2f}"
    if rec["supplier_id"] in ("S-09", "S-10"):
        return s.translate(ARABIC_DIGITS)
    if rec["supplier_id"] == "S-11":
        return s.replace(".", ",")
    return s


def make_supplier_feed(rng, api, original_costs):
    """What the API serves: one line per version of a record, ordered by updated_at."""
    rows = []
    for rec in api:
        first = {k: v for k, v in rec.items() if k != "corrected_at"}
        if "corrected_at" in rec:
            first["cost"] = original_costs[rec["price_id"]]
        rows.append(first)
        if "corrected_at" in rec:
            fix = {k: v for k, v in rec.items() if k != "corrected_at"}
            fix["updated_at"] = rec["corrected_at"]
            rows.append(fix)
    out = []
    for r in sorted(rows, key=lambda r: (r["updated_at"], r["price_id"])):
        o = {"price_id": r["price_id"], "product_id": r["product_id"], "supplier_name": r["supplier_name"],
             "cost": text_cost(rng, r), "currency": r["currency"], "unit": r["unit"], "valid_from": r["valid_from"],
             "updated_at": iso(r["updated_at"])}
        if r["updated_at"] >= INCOTERM_FROM:
            o["incoterm"] = "DAP" if r["currency"] == "SAR" else rng.choice(["CIF", "FOB"])
        out.append(o)
    return out


def make_orders(rng, customers, products):
    orders, lines = [], []
    cust_w = [(c, rng.paretovariate(1.6)) for c in customers]
    disc = {c["customer_id"]: rng.choice([0, 0, 0, 2, 5]) for c in customers}
    oid = 50000
    d = START
    while d <= END:
        n = int(rng.gauss(62 if d.weekday() != 4 else 30, 6))
        for _ in range(max(n, 5)):
            oid += 1
            c = weighted(rng, cust_w)[0]
            created = datetime(d.year, d.month, d.day, rng.randint(7, 21), rng.randint(0, 59), tzinfo=RIYADH)
            status = "cancelled" if rng.random() < .04 else "confirmed"
            updated = created + (timedelta(hours=rng.randint(1, 30)) if status == "cancelled" else timedelta(0))
            orders.append({"order_id": oid, "customer_id": c["customer_id"], "order_date": d.isoformat(),
                           "status": status, "created_at": iso(created), "updated_at": iso(updated)})
            avail = [p for p in products if not (p["supplier_id"] == "S-12" and d >= date(2026, 10, 10))]
            for ln, p in enumerate(rng.sample(avail, rng.randint(1, 6)), start=1):
                carton = rng.random() < .85
                qty = rng.randint(1, 20) if carton else rng.randint(1, 48)
                price = round(p["list_price_piece_sar"] * (p["units_per_carton"] if carton else 1), 2)
                lines.append({"order_id": oid, "line_no": ln, "product_id": p["product_id"],
                              "unit": "carton" if carton else "piece", "qty": qty, "unit_price_sar": price,
                              "discount_pct": disc[c["customer_id"]]})
        d += timedelta(days=1)
    return orders, lines


def make_shipments(rng, orders, cust_city, lines):
    value = {}
    for ln in lines:
        value[ln["order_id"]] = value.get(ln["order_id"], 0) + ln["qty"] * ln["unit_price_sar"]
    base = {"Jeddah": 35, "Riyadh": 85, "Dammam": 110, None: 60}
    days = {"Jeddah": (0, 1), "Riyadh": (1, 2), "Dammam": (1, 3), None: (1, 2)}
    out = []
    for o in orders:
        if o["status"] != "confirmed":
            continue
        city = cust_city.get(o["customer_id"])
        created = datetime.fromisoformat(o["created_at"])
        shipped = (created + timedelta(days=rng.randint(0, 1))).replace(hour=rng.randint(8, 16), minute=rng.randint(0, 59))
        if shipped < created:
            shipped = created + timedelta(hours=2)
        delivered = shipped + timedelta(days=rng.randint(*days[city]), hours=rng.randint(1, 8))
        out.append({"shipment_id": f"SH-{o['order_id']}", "order_id": o["order_id"], "carrier": rng.choice(CARRIERS),
                    "city": city or "Unknown", "shipped_at": iso(shipped), "delivered_at": iso(delivered),
                    "freight_sar": round(base[city] + .006 * value.get(o["order_id"], 0), 2)})
    return out


def make_events(rng, shipments):
    ev, n = [], 0
    for s in shipments:
        shipped = datetime.fromisoformat(s["shipped_at"])
        if shipped.date() < STREAM_FROM:
            continue
        for status, t in (("picked", shipped - timedelta(hours=2)), ("departed", shipped),
                          ("delivered", datetime.fromisoformat(s["delivered_at"]))):
            if t >= datetime(2026, 11, 1, tzinfo=RIYADH):
                continue
            n += 1
            r = rng.random()
            delay = (timedelta(minutes=rng.randint(0, 10)) if r < .90 else
                     timedelta(hours=rng.randint(1, 6)) if r < .97 else timedelta(days=rng.randint(1, 3)))
            e = {"event_id": f"EV-{n:06d}", "shipment_id": s["shipment_id"], "order_id": s["order_id"], "city": s["city"],
                 "status": status, "event_time": iso(t), "arrived_at": t + delay}
            ev.append(e)
            if rng.random() < .02:
                ev.append(dict(e, arrived_at=e["arrived_at"] + timedelta(minutes=rng.randint(1, 90))))
    ev.sort(key=lambda e: (e["arrived_at"], e["event_id"]))
    for e in ev:
        e["arrived_at"] = iso(e["arrived_at"])
    return ev


def make_supplier_cdc(rng, suppliers):
    """A Debezium-style change feed over the supplier table, from the 1 August snapshot to 31 October."""
    state = {s["supplier_id"]: dict(s) for s in suppliers}
    changes = []

    def at(d: date, h: int) -> datetime:
        return datetime(d.year, d.month, d.day, h, rng.randint(0, 59), tzinfo=RIYADH)

    plan = []
    for _ in range(30):
        sid = rng.choice([s["supplier_id"] for s in suppliers if s["supplier_id"] not in ("S-07", "S-12")])
        field = rng.choice(["payment_terms_days", "contact_email", "contact_name"])
        plan.append((at(START + timedelta(days=rng.randint(0, 90)), rng.randint(8, 17)), "u", sid, field))
    plan.append((at(date(2026, 9, 1), 9), "u", "S-07", "country"))
    plan.append((at(date(2026, 8, 20), 10), "u", "S-05", "name_en"))
    plan.append((at(date(2026, 10, 10), 11), "d", "S-12", None))
    for sid, en, ar, country, ccy, d in NEW_SUPPLIERS:
        plan.append((at(d, 10), "c", sid, (en, ar, country, ccy)))
    plan.sort(key=lambda p: p[0])
    lsn = 7_000_000
    for when, op, sid, field in plan:
        lsn += rng.randint(100, 900)
        before = dict(state[sid]) if sid in state else None
        if op == "u":
            after = dict(before)
            if field == "payment_terms_days":
                after[field] = rng.choice([v for v in (30, 45, 60, 90) if v != before[field]])
            elif field == "contact_email":
                after[field] = f"accounts{rng.randint(2, 9)}@{before['name_en'].lower().replace(' ', '-')}.example"
            elif field == "contact_name":
                after[field] = f"{rng.choice(FIRST)} {rng.choice(FAMILY)}"
            elif field == "country":
                after.update(country="SA", currency="SAR")
            elif field == "name_en":
                after.update(name_en="Bayader Paper and Packaging")
            state[sid] = after
        elif op == "c":
            en, ar, country, ccy = field
            after = {"supplier_id": sid, "name_en": en, "name_ar": ar, "country": country, "currency": ccy,
                     "payment_terms_days": 60, "contact_name": f"{rng.choice(FIRST)} {rng.choice(FAMILY)}",
                     "contact_email": f"sales@{en.lower().replace(' ', '-')}.example",
                     "iban": f"SA{rng.randint(10, 99)}{rng.randint(0, 10**18 - 1):018d}",
                     "contract_ref": f"QT-CON-2026-{int(sid[2:]):03d}"}
            state[sid] = after
        else:
            after = None
            del state[sid]
        ts = int(when.timestamp() * 1000)
        changes.append({"op": op, "before": before if op != "c" else None, "after": after,
                        "source": {"table": "suppliers", "lsn": lsn, "ts_ms": ts}, "ts_ms": ts + rng.randint(200, 4000)})
    # delivery problems: three events re-sent, two neighbours for one supplier swapped in arrival order
    feed = list(changes)
    for e in rng.sample(changes[:-3], 3):
        feed.append(dict(e, ts_ms=e["ts_ms"] + 3_600_000))
    same = [i for i in range(len(changes) - 1) for j in range(i + 1, len(changes))
            if changes[i]["op"] == "u" and changes[j]["op"] == "u" and
            changes[i]["before"]["supplier_id"] == changes[j]["before"]["supplier_id"]]
    i = same[len(same) // 2]
    sid = changes[i]["before"]["supplier_id"]
    j = next(k for k in range(i + 1, len(changes)) if changes[k]["op"] == "u" and changes[k]["before"]["supplier_id"] == sid)
    a, b = feed[i], feed[j]
    feed[i] = dict(a, ts_ms=b["ts_ms"] + 1000)        # the older change arrives after the newer one
    feed.sort(key=lambda e: e["ts_ms"])
    return feed, changes, state, sid


def scd2(suppliers, changes):
    """The reference type 2 history: one row per version, valid_from inclusive, valid_to exclusive."""
    rows, cur = [], {}
    for s in suppliers:
        cur[s["supplier_id"]] = dict(s, valid_from="2026-08-01T00:00:00+03:00")
    for e in sorted(changes, key=lambda e: e["source"]["lsn"]):
        when = iso(datetime.fromtimestamp(e["source"]["ts_ms"] / 1000, RIYADH))
        sid = (e["after"] or e["before"])["supplier_id"]
        if sid in cur:
            rows.append(dict(cur.pop(sid), valid_to=when))
        if e["after"] is not None:
            cur[sid] = dict(e["after"], valid_from=when)
    rows += [dict(v, valid_to=None) for v in cur.values()]
    return sorted(rows, key=lambda r: (r["supplier_id"], r["valid_from"]))


# ------------------------------------------------------------------------------------------------ answers
def answers(orders, lines, products, erp, customers, shipments, history):
    prod = {p["product_id"]: p for p in products}
    cust = {c["customer_id"]: c for c in customers}
    prices: dict[str, list] = {}
    for r in erp:
        prices.setdefault(r["product_id"], []).append(r)

    def cost_on(pid, d):
        for r in prices[pid]:
            if r["valid_from"] <= d and (not r["valid_to"] or d <= r["valid_to"]):
                return r["cost_piece_sar"]
        raise KeyError((pid, d))

    def country_on(sid, ts):
        for r in history:
            if r["supplier_id"] == sid and r["valid_from"] <= ts and (r["valid_to"] is None or ts < r["valid_to"]):
                return r["country"]
        return "Unknown"

    order = {o["order_id"]: o for o in orders}
    freight = {s["order_id"]: s["freight_sar"] for s in shipments}
    fact = []
    for ln in lines:
        o = order[ln["order_id"]]
        if o["status"] != "confirmed":
            continue
        p = prod[ln["product_id"]]
        pieces = ln["qty"] * (p["units_per_carton"] if ln["unit"] == "carton" else 1)
        rev = round(ln["qty"] * ln["unit_price_sar"] * (1 - ln["discount_pct"] / 100), 2)
        cost = round(pieces * cost_on(p["product_id"], o["order_date"]), 2)
        c = cust.get(o["customer_id"])
        fact.append({"order_id": o["order_id"], "month": o["order_date"][:7], "revenue": rev, "cost": cost,
                     "category": p["category"], "city": c["city"] if c else "Unknown",
                     "customer_type": c["customer_type"] if c else "Unknown",
                     "country": country_on(p["supplier_id"], o["created_at"])})
    order_rev = {}
    for f in fact:
        order_rev[f["order_id"]] = order_rev.get(f["order_id"], 0) + f["revenue"]
    for f in fact:
        f["freight"] = freight[f["order_id"]] * f["revenue"] / order_rev[f["order_id"]]

    def group(keys, rows, extra=False):
        g = {}
        for f in rows:
            k = tuple(f[x] for x in keys)
            a = g.setdefault(k, {"revenue": 0.0, "cost": 0.0, "freight": 0.0})
            for m in a:
                a[m] += f[m]
        out = []
        for k, a in sorted(g.items()):
            r = dict(zip(keys, k))
            r.update(revenue=round(a["revenue"], 2), cost=round(a["cost"], 2), margin=round(a["revenue"] - a["cost"], 2),
                     margin_pct=round(100 * (a["revenue"] - a["cost"]) / a["revenue"], 2))
            if extra:
                r.update(freight=round(a["freight"], 2), margin_after_freight=round(a["revenue"] - a["cost"] - a["freight"], 2))
            out.append(r)
        return out

    return {"q1_monthly": group(["month"], fact), "q2_type_city": group(["customer_type", "city"], fact),
            "q3_country_at_order": group(["country"], fact), "q4_category_month": group(["category", "month"], fact),
            "q5_city_after_freight": group(["city"], fact, extra=True)}


def old_report(orders, lines, extract_lines, products, erp):
    """What the current report computes: every order status, every extract line (with the re-sent batch)."""
    prod = {p["product_id"]: p for p in products}
    prices: dict[str, list] = {}
    for r in erp:
        prices.setdefault(r["product_id"], []).append(r)
    order = {o["order_id"]: o for o in orders}
    g = {}
    for ln in extract_lines:
        o, p = order[ln["order_id"]], prod[ln["product_id"]]
        d = o["order_date"]
        cp = next(r["cost_piece_sar"] for r in prices[p["product_id"]] if r["valid_from"] <= d and (not r["valid_to"] or d <= r["valid_to"]))
        rev = ln["qty"] * ln["unit_price_sar"] * (1 - ln["discount_pct"] / 100)
        cost = ln["qty"] * (p["units_per_carton"] if ln["unit"] == "carton" else 1) * cp
        a = g.setdefault(d[:7], [0.0, 0.0])
        a[0] += rev
        a[1] += cost
    return [{"month": m, "revenue": round(a[0], 2), "cost": round(a[1], 2), "margin": round(a[0] - a[1], 2),
             "margin_pct": round(100 * (a[0] - a[1]) / a[0], 2)} for m, a in sorted(g.items())]


# ------------------------------------------------------------------------------------------------ writers
def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


def write_sqlite(path: Path, tables: dict[str, list[dict]]) -> None:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    for name, rows in tables.items():
        cols = list(rows[0])
        con.execute(f"CREATE TABLE {name} ({', '.join(cols)})")
        con.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})", [tuple(r[c] for c in cols) for r in rows])
    con.execute("CREATE INDEX ix_orders_customer ON orders(customer_id)")
    con.execute("CREATE UNIQUE INDEX ix_orders_id ON orders(order_id)")
    con.execute("CREATE INDEX ix_lines_order ON order_lines(order_id)")
    con.commit()
    con.close()


def main(force: bool = False) -> Path:
    if (REF / "finance_answers.json").exists() and not force:
        return RAW
    rng = random.Random(SEED)
    customers = make_customers(rng)
    suppliers = make_suppliers(rng)
    products = make_products(rng)
    api = make_prices(rng, products, suppliers)
    original = {}
    for rec in api:
        original[rec["price_id"]] = rec["cost"]
    for rec in api:                                  # corrections carry a new cost; the first version keeps the old one
        if "corrected_at" in rec:
            original[rec["price_id"]] = round(rec["cost"] / rng.choice([.97, 1.03, 1.05]), 2)
    erp = []
    units = {p["product_id"]: p["units_per_carton"] for p in products}
    by_product: dict[str, list] = {}
    for rec in api:
        by_product.setdefault(rec["product_id"], []).append(rec)
    for pid, recs in sorted(by_product.items()):
        recs.sort(key=lambda r: r["valid_from"])
        for j, rec in enumerate(recs):
            per = units[pid] if rec["unit"] == "carton" else 1
            vt = (date.fromisoformat(recs[j + 1]["valid_from"]) - timedelta(days=1)).isoformat() if j + 1 < len(recs) else ""
            erp.append({"product_id": pid, "supplier_id": rec["supplier_id"],
                        "cost_piece_sar": round(rec["cost"] * RATES[rec["currency"]] / per, 2),
                        "valid_from": rec["valid_from"], "valid_to": vt})
    feed = make_supplier_feed(rng, api, original)
    orders, lines = make_orders(rng, customers, products)
    cust_city = {c["customer_id"]: c["city"] for c in customers if c["customer_id"] != ERASED}
    shipments = make_shipments(rng, orders, cust_city, lines)
    events = make_events(rng, shipments)
    cdc, changes, final_state, swapped = make_supplier_cdc(rng, suppliers)
    history = scd2(suppliers, changes)
    kept = [c for c in customers if c["customer_id"] != ERASED]
    dup_ids = {o["order_id"] for o in orders if o["order_date"] == DUP_DAY.isoformat()}
    extract_lines = lines + [ln for ln in lines if ln["order_id"] in dup_ids]

    # November batch of the supplier feed: the producer renamed a column and sent one negative cost
    nov = list({r["price_id"]: dict(r) for r in feed[-40:]}.values())     # one version per price in a batch
    for r in nov:
        r["updated_at"] = "2026-11-01T06:00:00+03:00"
    broken = [{("unit_cost" if k == "cost" else k): v for k, v in r.items()} for r in nov]
    broken[7]["unit_cost"] = "-" + str(broken[7]["unit_cost"])

    RAW.mkdir(parents=True, exist_ok=True)
    write_sqlite(RAW / "qafila_orders.sqlite", {"customers": kept, "products": products, "orders": orders,
                                                 "order_lines": lines})
    write_csv(RAW / "extracts" / "orders.csv", orders)
    write_csv(RAW / "extracts" / "order_lines.csv", extract_lines)
    write_csv(RAW / "extracts" / "customers.csv", kept)
    write_csv(RAW / "extracts" / "products.csv", products)
    write_csv(RAW / "extracts" / "prices.csv", erp)
    write_jsonl(RAW / "extracts" / "shipments.jsonl", shipments)
    write_jsonl(RAW / "supplier_api" / "price_records.jsonl", feed)
    write_jsonl(RAW / "supplier_api" / "batch_2026-11-01.jsonl", broken)
    write_jsonl(RAW / "supplier_api" / "batch_2026-11-01_fixed.jsonl", nov)
    write_csv(RAW / "suppliers" / "suppliers_2026-08-01.csv", suppliers)
    write_jsonl(RAW / "suppliers" / "supplier_changes.jsonl", cdc)
    write_csv(RAW / "suppliers" / "suppliers_2026-10-31.csv", sorted(final_state.values(), key=lambda r: r["supplier_id"]))
    write_csv(RAW / "customers_2026-09-30.csv", customers)       # last quarter's customer snapshot, before the erasure
    write_jsonl(RAW / "events" / "shipment_events.jsonl", events)

    fa = answers(orders, lines, products, erp, kept, shipments, history)
    write_json(REF / "finance_answers.json", fa)
    write_csv(REF / "monthly_margin.csv", fa["q1_monthly"])
    write_csv(REF / "margin_report_old.csv", old_report(orders, lines, extract_lines, products, erp))
    write_csv(REF / "dim_supplier.csv", [{k: ("" if v is None else v) for k, v in r.items()} for r in history])
    delivered = {}
    for s in shipments:
        d = s["delivered_at"][:10]
        if STREAM_FROM.isoformat() <= d <= "2026-10-31":
            delivered[d] = delivered.get(d, 0) + 1
    write_json(REF / "facts.json", {
        "orders": len(orders), "confirmed": sum(o["status"] == "confirmed" for o in orders),
        "cancelled": sum(o["status"] == "cancelled" for o in orders), "lines": len(lines),
        "extract_lines": len(extract_lines), "duplicate_lines": len(extract_lines) - len(lines),
        "orphan_orders": sum(o["customer_id"] == ERASED for o in orders), "products": len(products),
        "customers": len(kept), "price_versions": len(erp), "api_records": len(feed),
        "api_first_release": sum(r["updated_at"] < iso(API_SPLIT) for r in feed),
        "api_corrections": len(feed) - len(api), "cdc_events": len(cdc), "cdc_changes": len(changes),
        "cdc_swapped_supplier": swapped, "dim_supplier_rows": len(history), "shipments": len(shipments),
        "events": len(events), "delivered_per_day": dict(sorted(delivered.items())),
    })
    return RAW


if __name__ == "__main__":
    out = main(force="--force" in sys.argv)
    facts = json.loads((REF / "facts.json").read_text(encoding="utf-8"))
    print("wrote", out.relative_to(LABS), {k: v for k, v in facts.items() if k != "delivered_per_day"})
