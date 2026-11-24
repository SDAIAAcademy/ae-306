---
course: "Modern Data Engineering"
code: "AE-306"
version: "2027.2.0"
deck: "day2"
day: 2
language: "en"
view: "trainee"
source: "https://sdaiaacademy.github.io/ae-306/slides/day2.html"
---

# Modern Data Engineering

## Day 2: Ingest and clean

#### [day2#title] Ingest and clean

*SDAIA Academy · Modern Data Engineering*

Day 2

AI Engineering Track · 4 teaching days + capstone day · 4 sessions · 4 labs · AE-306

#### [day2#agenda] Ingest and clean

*Today*

- **Session 1 · Ingesting from APIs**: Pages, cursors, rate limits and loads that can run twice
- **Session 2 · Declarative ingestion pipelines**: The same load as a declared resource: cursor, merge, schema evolution and load state
- **Session 3 · Change data capture, merge and history**: Change events, ordering by log position, MERGE, and supplier history as a type 2 dimension
- **Session 4 · Cleaning with dataframes**: Expressions, lazy plans and cleaning rules kept as data, with a log of what each rule changed

#### [day2#review-day-1] The re-sent batch, one day later

*Review of Day 1*

**Question:** Tonight's extract re-sends the lines of 2 November, as it did for 14 September. Which rule in your margin query keeps the report right without anyone noticing?

- A. Exclude the lines of 14 September
- B. Keep one row per order and line number
- C. Keep confirmed orders only
- D. Report the margin percentage only

### Session 1: Ingesting from APIs

#### [day2#s1] Ingesting from APIs

*Session 1*

- Follow every page of a cursor-paginated API
- Back off on 429 responses
- Store load state with the data so a re-run adds nothing

#### [day2#supplier-api-shape] Twenty records a page, a cursor to the next, and a 429 every few calls

*Qafila's supplier price API*

```json
// file: GET /prices?updated_since=…
{"data": [{"price_id": "PR-00009", "product_id": "P-1006",
           "supplier_name": "مؤسسة حبوب الحجاز", "cost": "81.22",
           "currency": "SAR", "unit": "carton",
           "valid_from": "2026-07-01", "updated_at": "2026-06-24T20:17:00+03:00"}, …],
 "next_cursor": "WyIiLCAyMF0="}
```

- Corrections come back later with the same `price_id` and a newer `updated_at`.
- The cursor is opaque: send it back, never parse it.

#### [day2#paging-and-backoff] Follow every page; on a 429, wait and repeat the same request

*Lab 2.1 · step 2*

```python
# file: fetch_since
while True:
    resp = requests.get(f"{base}/prices", params=params, timeout=10)
    if resp.status_code == 429:
        time.sleep(float(resp.headers.get("Retry-After", "1")))
        continue                       # same params: same page
    resp.raise_for_status()
    page = resp.json(); records += page["data"]
    if not page["next_cursor"]:
        break
    params = {"cursor": page["next_cursor"]}
```

#### [day2#two-decisions-idempotent] A key and a stored cursor make a load safe to repeat

*Loads that can run twice*

- **A key for one record version.** `(price_id, updated_at)`, enforced on insert. A version loaded twice is stored once.
- **The cursor stored with the data.** The highest `updated_at` loaded, in a table of the same database. The next run asks only for what is newer.

> **Idempotent** means running it again changes nothing. Retries, restarts and backfills all depend on it.

#### [day2#rerun-adds-nothing] The second run adds nothing; new data adds exactly the new versions

*Lab 2.1 · step 4*

| Run | Rows inserted | Requests |
| --- | --- | --- |
| First, API as of 15 October | 99 | 7 |
| Again, nothing new | 0 | 1 |
| After 31 October | 28: 3 new prices, 25 corrections | 2 |

Raw keeps both versions of each corrected price: 102 prices, 127 versions.

#### [day2#rows-and-cursor-together] Store the rows and the cursor in one transaction

*The failure in between*

**BEGIN** → **Insert** new versions → **Update** the cursor → **COMMIT**

Cursor first and a crash loses data silently. Rows first and a crash re-reads, which the key absorbs. Both together and neither can happen.

#### [day2#checkpoint-1] The doubled table

*Checkpoint*

**Question:** A colleague's supplier load stores the cursor correctly, but after a crash and a re-run the table holds twice the rows for one day. Which decision was missing?

- A. A smaller page size
- B. Keeping the cursor in a file
- C. More retries on 429
- D. A key on the record version, enforced on insert

#### [day2#lab-2-1] An incremental, idempotent API load

Lab 2.1 · 25 min

Load the paginated supplier price API into DuckDB with a stored cursor, survive rate limits, and show that a re-run adds no duplicates.

[D2_1_api_ingestion.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D2_1_api_ingestion.ipynb)

- [ ] One request: read the page and the cursor (4 min)
- [ ] Follow every page, back off on 429 (7 min)
- [ ] Load with a key and a stored cursor (8 min)
- [ ] Run it twice, then after new data (6 min)
- [ ] ✱ Stretch: Keep the rows and the cursor in one transaction

### Session 2: Declarative ingestion pipelines

#### [day2#s2] Declarative ingestion pipelines

*Session 2*

- Declare a REST resource with an incremental cursor and a primary key
- Absorb a new source column and find it in the schema
- Read a pipeline's load state and load history

#### [day2#declare-not-write] Declare the key, the cursor and the merge; the library does the rest

*Declarative ingestion*

```python
# file: Lab 2.2 · step 1
@dlt.resource(name="supplier_prices", primary_key="price_id",
              write_disposition="merge")
def supplier_prices(base_url,
                    updated_at=dlt.sources.incremental("updated_at", initial_value="")):
    params = {"updated_since": updated_at.last_value}
    … # the same paging loop as Lab 2.1
    yield page["data"]

pipeline.run(supplier_prices(api.url))
```

#### [day2#dlt-state-and-loads] The library stores what you wrote by hand: state and load history

*Lab 2.2 · step 2*

| Table in the destination | Holds | In Lab 2.1 |
| --- | --- | --- |
| `supplier_prices` | the data, plus `_dlt_load_id` on each row | raw.supplier_prices |
| `_dlt_pipeline_state` | the cursor (`last_value`) | raw._load_state |
| `_dlt_loads` | one row per load package, with its status | nothing |
| `_dlt_version` | each version of the schema | nothing |

#### [day2#schema-evolution] In October the supplier adds a column, and the table grows one

*Lab 2.2 · step 3*

- First run (API as of September): 93 prices, no `incoterm`.
- Second run: the column appears in the table and in a new schema version.
- Older rows hold NULL: no value existed when they were sent.

| incoterm | prices |
| --- | --- |
| CIF | 10 |
| DAP | 9 |
| FOB | 15 |
| NULL | 68 |

#### [day2#evolve-or-freeze] Evolve in raw; decide on purpose everywhere after it

*What should a pipeline do with a new column?*

- **evolve.** Add the column. Nothing is lost. The default.
- **freeze.** Fail the load. Someone decides.
- **discard value.** Load the row, drop the field.
- **discard row.** Skip the whole record.

The stretch of Lab 2.2 freezes the columns: a record with an unknown field fails the load and the table is unchanged.

#### [day2#merge-proves-itself] Prove the merge against the source, not against the library's word

*Lab 2.2 · step 4*

- **102** prices stored
- **0** duplicate price ids
- **0** prices not at their latest version

The reference is computed from the source file: the latest version of each price id. The 25 corrections are applied.

#### [day2#checkpoint-2] The column that appeared

*Checkpoint*

**Question:** The supplier API starts sending `incoterm`. Qafila's raw layer and its margin mart both read the feed. What should happen in each?

- A. Raw adds the column; the mart waits until a model uses it
- B. Raw drops it; the mart adds it
- C. Both fail until someone approves
- D. Both add it automatically

#### [day2#lab-2-2] The supplier load with dlt

Lab 2.2 · 25 min

Rebuild the supplier price load with dlt, absorb the new incoterm column, and inspect the stored state and load history.

[D2_2_dlt_pipeline.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D2_2_dlt_pipeline.ipynb)

- [ ] Declare the resource and run the pipeline (7 min)
- [ ] Read what was created: tables, columns, state (5 min)
- [ ] New data with a new column: run again (7 min)
- [ ] Prove the merge: no duplicates, corrections applied (6 min)
- [ ] ✱ Stretch: Freeze the schema and watch the next new column fail

### Session 3: Change data capture, merge and history

#### [day2#s3] Change data capture, merge and history

*Session 3*

- Read a change event envelope and order events by log position
- Apply updates and deletes to a copy with MERGE
- Keep history as a type 2 dimension with valid ranges

#### [day2#log-based-cdc] Read the database's log, not its tables

*Change data capture*

1. **Supplier table** procurement edits
2. **Write-ahead log** every committed change
3. **Change events** c, u, d with before and after
4. **Your copy** merged, and history

Polling the table with "changed since" misses deletes and every change between two polls. The log has all of them, in commit order.

#### [day2#change-event-envelope] The envelope carries the row before, the row after and the log position

*One change event*

```json
// file: supplier_changes.jsonl
{"op": "u",
 "before": {"supplier_id": "S-07", "country": "AE", "currency": "AED", …},
 "after":  {"supplier_id": "S-07", "country": "SA", "currency": "SAR", …},
 "source": {"table": "suppliers", "lsn": 7006317, "ts_ms": 1788242880000},
 "ts_ms": 1788242880298}
```

- `source.lsn`: the order the database committed. `ts_ms` outside: when the event was sent.
- A delete has `after` null; a create has `before` null.

#### [day2#order-by-log-position] Delivery repeats and reorders; the log position does not

*Lab 2.3 · step 1*

| Arrival | lsn | Change to supplier S-15 |
| --- | --- | --- |
| 11 | 7,005,180 | e-mail becomes accounts6@… |
| 12 | **7,004,499** | payment terms 30 days (older) |
| 13 | 7,005,956 | e-mail becomes accounts7@… |

38 events: 3 delivered twice, 1 after a newer change. Applied by arrival, event 12 would put the old e-mail back.

#### [day2#merge-latest-state] MERGE applies the latest change per supplier in one statement

*Lab 2.3 · step 2*

```sql
-- file: DuckDB
MERGE INTO suppliers AS t USING latest AS s
  ON t.supplier_id = s.sid
WHEN MATCHED AND s.op = 'd' THEN DELETE
WHEN MATCHED THEN UPDATE SET name_en = s.name_en, country = s.country, …
WHEN NOT MATCHED AND s.op <> 'd' THEN INSERT (…) VALUES (…)
```

18 suppliers, S-12 deleted, S-19 and S-20 created: 19 rows, and `EXCEPT` both ways against the source finds nothing.

#### [day2#scd-type-2] A type 2 dimension keeps one row per version, with a validity range

*History*

| supplier | country | valid_from | valid_to |
| --- | --- | --- | --- |
| S-07 | AE | 1 Aug | 1 Sep |
| S-07 | SA | 1 Sep | (current) |
| S-12 | TR | 1 Aug | 10 Oct (deleted) |

52 versions, 19 current, no overlapping ranges. `valid_from` inclusive, `valid_to` exclusive: every moment belongs to one version.

#### [day2#checkpoint-3] Two events, which one wins?

*Checkpoint*

**Question:** Two updates for supplier S-15 reach your pipeline. The second to arrive has a lower log position than the first. Which one should your copy keep?

- A. The one that arrived last
- B. The one with the later outer ts_ms
- C. The one with the higher log position
- D. Either: they will reconcile later

#### [day2#lab-2-3] Supplier changes and their history

Lab 2.3 · 25 min

Apply the supplier change feed of updates and deletes, reconcile with the source, and keep supplier history as a slowly changing dimension with correct validity ranges.

[D2_3_cdc_scd.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D2_3_cdc_scd.ipynb)

- [ ] Read the feed: duplicates and out-of-order events (5 min)
- [ ] Latest state per supplier with MERGE (7 min)
- [ ] Reconcile with the source snapshot (4 min)
- [ ] Type 2 history with valid ranges (9 min)
- [ ] ✱ Stretch: As-of join: margin by supplier country at order time

### Session 4: Cleaning with dataframes

#### [day2#s4] Cleaning with dataframes

*Session 4*

- Write cleaning steps as Polars expressions
- Convert currencies and units to one cost per piece in SAR
- Normalise Arabic names and log every rule with the rows it changed

#### [day2#polars-expressions] A Polars expression is a rule you can name, run and log

*Cleaning with dataframes*

```python
# file: Lab 2.4 · step 2
RULES = [
  ("digits", "cost_text", pl.col("cost").str.strip_chars()
      .str.replace_many(list("٠١٢٣٤٥٦٧٨٩٫"), list("0123456789."))
      .str.replace(",", ".", literal=True)),
  ("to_sar", "cost_sar", pl.col("cost_text").cast(pl.Float64)
      * pl.col("currency").replace_strict(RATES, return_dtype=pl.Float64)),
]
```

#### [day2#raw-prices-profile] 102 prices, three currencies, two units, 56 spellings of 18 suppliers

*Lab 2.4 · step 1*

| Cost as sent | Means |
| --- | --- |
| `81.22` | 81.22 |
| `٣٫٣٣` | 3.33, Arabic-Indic digits |
| `36,09` | 36.09, decimal comma |

- 21 costs are not plain decimals.
- USD at 3.75 and AED at 1.0211 riyals: the course's fixed rates.
- Most prices are per carton; cost per piece needs the product's units per carton.

#### [day2#arabic-normalisation] Five rules turn 56 spellings into 18 supplier ids

*Lab 2.4 · step 4*

| Rule | Example |
| --- | --- |
| Trim spaces | " أرز كيرلا " to "أرز كيرلا" |
| Drop a company prefix | "شركة", "مؤسسة" |
| Remove tatweel | "كيرلـا" to "كيرلا" |
| One alef | أ إ آ to ا |
| One final taa | ة to ه |

Normalise both sides the same way, then join. Every record must map, and to its product's supplier.

#### [day2#rule-log-reconcile] The rule log says what changed; the reconciliation says it was right

*Lab 2.4 · step 5*

| Rule | Rows changed |
| --- | --- |
| digits | 21 |
| to_sar | 102 |
| per_piece | 102 |
| supplier_id | 102 mapped |

- **Against the ERP price list.** All 102 prices match procurement's cost per piece; one differs by one halala of rounding.

#### [day2#checkpoint-4] Where rounding goes

*Checkpoint*

**Question:** A price is 61.99 USD per carton of 6. Your colleague converts to riyals, rounds to two decimals, then divides by 6 and rounds again. The ERP shows a different halala. What do you change?

- A. Divide by 6 before converting the currency
- B. Round once, after both steps
- C. Round the ERP's value the same way
- D. Store the cost as a 64-bit float

#### [day2#lab-2-4] Currencies, units and Arabic names

Lab 2.4 · 25 min

Clean the supplier prices with Polars: currencies, units, Arabic supplier names and Arabic-Indic digits, logging every rule applied, then reconcile with the ERP price list.

[D2_4_cleaning.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D2_4_cleaning.ipynb)

- [ ] Profile the raw prices (4 min)
- [ ] Digits and currencies (6 min)
- [ ] Units: cartons to pieces (5 min)
- [ ] Arabic supplier names to one id (6 min)
- [ ] The rule log and the reconciliation (4 min)
- [ ] ✱ Stretch: The same rules as a lazy plan: read the optimised plan

#### [day2#day-2-recap] Three things to keep from today

*Day 2*

- **Loads that can run twice.** A key on the version and a cursor stored with the data, in one transaction.
- **The log decides the order.** Deduplicate and order change events by log position; keep history as versions with ranges.
- **Rules you can count.** Each cleaning rule named, logged and reconciled with a reference.

#### [day2#tomorrow-model-test] Tomorrow the cleaned data becomes finance's star schema, tested and scheduled

*Day 3 · Model and test*

- Grain first: one row per line of a confirmed order
- Models as SQL files in git, rebuilt only where they changed
- A contract on the supplier feed that holds when the feed breaks at night

Before tomorrow: read finance's five margin questions in `labs/data/reference/finance_answers.json`.
