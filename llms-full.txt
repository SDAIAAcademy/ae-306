---
course: "Modern Data Engineering"
code: "AE-306"
version: "2027.1.0"
scope: "course"
language: "en"
view: "trainee"
source: "https://sdaiaacademy.github.io/ae-306/"
---

# Modern Data Engineering

Build one batch pipeline from raw extracts to a tested, governed open table that two engines read

Participants build one batch pipeline end to end for Qafila, the fictional trading company of the Academy's data engineering course, whose margin report nobody trusts. They query raw extracts with analytical SQL, ingest an API and a database change feed incrementally, clean with dataframes, model a star schema with a slowly changing supplier dimension, write tested transformations and a data contract, orchestrate them, and land the result in an open table format that a second engine reads. Day four adds distributed processing, streaming and governance.

- **Audience:** Practitioners: engineers and analysts who already write SQL and work with Python dataframes, and who now need a batch pipeline that is incremental, tested, held by a contract and governed.
- **Prerequisites:** FN-102 Command Line, Git and Reproducible Projects; FN-104 SQL and Data Wrangling; Writes SQL joins, grouping and simple window functions; Filters and joins tables with a Python dataframe library; Commits with Git from a shell; Setup: a laptop CPU with uv, or Google Colab. No model, no key, no Docker, no cloud account. Run 00_setup_check before Day 1; see labs/README.md.
- **Case study:** Qafila Trading: Qafila Trading is a fictional importer and wholesaler of food and household goods in Jeddah, Riyadh and Dammam, selling to 240 shops, restaurants and hotels and buying from 18 suppliers in five countries. Its finance controller, Lujain Al-Zamil, does not trust the monthly margin report. Participants rebuild it as one pipeline: order extracts, a paginated supplier price API, a supplier change feed and a shipment event stream, all synthetic, generated with a fixed seed and planted with the problems the labs find.

## Outcomes

- LO1 (Applied): Analyse raw transactional extracts with analytical SQL, including window functions and incremental predicates, given three months of synthetic orders, shipments and prices in columnar files
- LO2 (Applied): Implement incremental ingestion from an API and a change feed, keeping supplier history as a slowly changing dimension, given a paginated API and a feed with updates and deletes
- LO3 (Performance): Design a dimensional model at a stated grain and build it as tested, version-controlled transformations, given the finance team's five margin questions
- LO4 (Performance): Build an orchestrated pipeline with a data contract, quality gates, retries and backfills that fails safely when an upstream feed breaks, given a supplier feed that changes its schema without notice
- LO5 (Applied): Configure an open table format with partitioning, schema evolution and time travel, and read it from a second engine, given the margin mart and one schema change
- LO6 (Applied): Classify every field under the national classification levels and apply minimisation, masking and access rules, given the customer and supplier tables

## Day 1: Store and query

#### [day1#title] Store and query

*SDAIA Academy · Modern Data Engineering*

Day 1

AI Engineering Track · 4 teaching days + capstone day · 4 sessions · 4 labs · AE-306

#### [day1#agenda] Store and query

*Today*

- **Session 1 · Platform shapes**: Transactional and analytical systems, ELT, and the layers of a lakehouse, placed on Qafila's workloads
- **Session 2 · Analytical SQL on a single node**: Query extracts in place with an in-process engine and reproduce a number before trusting it
- **Session 3 · Window functions**: Running totals, changes from the previous row and first and last per group, without collapsing rows
- **Session 4 · Columnar files and partitioning**: Parquet, row-group statistics and partitions, measured in time and bytes

### Session 1: Platform shapes

#### [day1#s1] Platform shapes

*Session 1*

- Tell a transactional workload from an analytical one by its access pattern
- Measure a point lookup and an aggregate on a row store and a column store
- Place a workload in a layer and justify it in one sentence

#### [day1#qafila-margin-problem] Qafila's margin report is wrong, and nobody can say by how much

*The case for the week*

- **Qafila Trading**: a fictional importer and wholesaler in Jeddah, Riyadh and Dammam
- 240 business customers, 18 suppliers in five countries, three currencies
- An order database, nightly extracts, a supplier price API, a change feed, shipment events
- All synthetic, written with a fixed seed: every number in this course can be reproduced

- **Lujain Al-Zamil.** Finance controller. Signs the monthly margin. Does not trust it.
- **Ammar Basri.** Procurement. Owns the supplier price feed.
- **Dalia Sabri.** Margin analyst. Reads the mart; must not read customer contacts.

#### [day1#two-access-patterns] The sales app and finance ask the same database opposite questions

*Transactional and analytical*

|  | Sales app (transactional) | Finance (analytical) |
| --- | --- | --- |
| Rows touched | a few, found by key | millions, scanned |
| Columns | all of one row | a few of every row |
| Writes | many small, concurrent | none, or a nightly batch |
| Who waits | a person, in milliseconds | a report, in seconds |

#### [day1#rows-or-columns] A row store keeps each order together; a column store keeps each field together

*Storage layout*

- **Row store (SQLite, PostgreSQL).** One read returns a whole order line. An index on `order_id` finds it without scanning. Summing one field reads every field.
- **Column store (DuckDB, warehouses).** A sum reads only `qty`, `unit_price_sar` and `discount_pct`, compressed and in batches. Fetching one whole row touches every column file.

#### [day1#lookup-vs-aggregate-measured] Each engine wins its own question by more than ten times

*Lab 1.1 · full run, 552,090 lines*

|  | Point lookup (one order) | Monthly aggregate |
| --- | --- | --- |
| SQLite (rows, indexed) | **0.04 ms** | 662 ms |
| DuckDB (columns) | 1.87 ms | **56 ms** |

Same lines, same SQL, one laptop. Your numbers will differ; the direction will not.

#### [day1#elt-load-then-transform] Copy first, transform where the analysis runs

*ELT*

**Extract** nightly copy of orders → **Load** unchanged, into raw → **Transform** SQL in the analytical engine

- Loading before transforming keeps the evidence: a wrong rule can be fixed and re-run on the raw copy.
- The transformation runs on the engine built for scans, not on the order database.

#### [day1#raw-staging-marts] Raw, staging and marts: each layer has one job

*Layered refinement*

- **Raw.** Exactly as received, dated, never edited. The extracts, the API pages, the change feed.
- **Staging.** Typed, deduplicated, one row per key. One model per source table.
- **Marts.** Facts and dimensions that answer finance's questions. Tested.

Some teams call them bronze, silver and gold. The names matter less than the rule: each layer reads only the one before.

#### [day1#warehouse-lake-lakehouse] Warehouse, lake, lakehouse: where the tables live and who can read them

*Three platform shapes*

| Shape | Storage | Read by | Good at |
| --- | --- | --- | --- |
| Warehouse | the engine's own format | that engine | modelled, tested tables; SQL |
| Lake | open files (Parquet, JSON) on object storage | any engine | cheap raw history; no tables, no transactions |
| Lakehouse | open files plus an open table format | several engines | tables with snapshots and schema changes over open files |

#### [day1#checkpoint-1] The dashboard on the order database

*Checkpoint*

**Question:** Finance points a dashboard at Qafila's order database and refreshes the monthly margin every five minutes. What breaks first?

- A. Nothing: the dashboard only reads
- B. The sales app slows down while the scans run
- C. The database runs out of disk
- D. The margin becomes correct because it is live

#### [day1#lab-1-1] Ten workloads, three layers

Lab 1.1 · 25 min

Time a point lookup and a monthly aggregate in SQLite and DuckDB, then place ten Qafila workloads in transactional, warehouse or lakehouse layers and justify each.

[D1_1_platform_shapes.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D1_1_platform_shapes.ipynb)

- [ ] Open the order database and the extracts (4 min)
- [ ] A point lookup and an aggregate, in both engines (7 min)
- [ ] Place ten workloads, with a reason each (10 min)
- [ ] Compare with the key and defend one difference (4 min)
- [ ] ✱ Stretch: Where would a nightly copy of the order database live, and why?

### Session 2: Analytical SQL on a single node

#### [day1#s2] Analytical SQL on a single node

*Session 2*

- Query CSV and JSON files in place with DuckDB
- Join lines to a price list valid on the order date
- Reproduce a reference figure and explain each difference

#### [day1#duckdb-in-process] DuckDB runs inside Python and reads files where they are

*An analytical engine in your notebook*

```python
# file: Lab 1.2
import duckdb
con = duckdb.connect()
con.sql("""
  SELECT status, count(*) AS orders
  FROM read_csv('data/raw/extracts/orders.csv')
  GROUP BY ALL""")
```

No server, no load step: a CSV, Parquet or JSON file is a table. The same SQL later runs on a warehouse.

#### [day1#profile-before-query] Profile the grain before you add anything up

*Before any sum*

- **18,630** lines in the extract
- **18,403** distinct (order, line) keys

Two questions first: what is one row (the grain), and do the keys say so? Here they do not: 227 lines are there twice.

#### [day1#joins-that-multiply] A join can multiply rows as easily as it drops them

*Joins*

| Join | What happens to the order lines |
| --- | --- |
| lines to orders on `order_id` | same count: each line has one order |
| lines to prices on `product_id` only | one row per price version: the count grows |
| orders to customers, inner | orders of an erased customer disappear |

> **Count before and after every join.** A join that changes the count without a reason you can state is a defect.

#### [day1#price-valid-on-date] Join each line to the price valid on its order date

*Cost at the right price*

```sql
-- file: Lab 1.2 · step 2
JOIN read_csv('prices.csv') AS pr
  ON pr.product_id = l.product_id
 AND o.order_date BETWEEN pr.valid_from
                     AND coalesce(pr.valid_to, DATE '9999-12-31')
```

- 58 products, 102 price versions: prices changed inside the quarter.
- Costing with today's price moves last month's margin every time procurement updates a price.
- Cartons become pieces first: `qty * units_per_carton`.

#### [day1#reproduce-before-trust] Summing every extract line reproduces the report nobody trusts

*Lab 1.2 · the gap*

| August | Revenue (SAR) | Margin % |
| --- | --- | --- |
| Old report | 23,219,590 | 24.23 |
| Finance's reference | 22,305,918 | 24.27 |

Revenue is 4.1 percent too high, and the percentage hides it: both revenue and cost are inflated together.

#### [day1#ai-off-lab] Lab 1.2 is done without an AI assistant

*How this lab runs*

- The evidence for this outcome is your queries and your note on two defects.
- Later labs allow an AI tutor for hints. Day 3 adds the skill that matters with assistants: verifying the SQL they write.
- The supervised entry and exit checks of SQL and modelling are AI-off too. Together they are 20% of your result.

- **Why.** You can only check a generated query if you can write and reason about one yourself.

#### [day1#checkpoint-2] Above the reference

*Checkpoint*

**Question:** Your September revenue is 7 percent above finance's reference and the margin percentage is almost the same. Which check do you run first?

- A. Compare every price with the ERP
- B. Check the currency conversion
- C. Count rows against distinct order-line keys
- D. Round each line before summing

#### [day1#lab-1-2] Reproduce the monthly margin

Lab 1.2 · 25 min

Query the raw extracts in place and reproduce finance's monthly margin without AI assistance; trace the gap to two defects and write them down.

[D1_2_margin_sql.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D1_2_margin_sql.ipynb)

- [ ] Read the extracts in place and profile them (5 min)
- [ ] Revenue and cost per line, with the price valid on the order date (8 min)
- [ ] The monthly margin against finance's reference (6 min)
- [ ] Find the two defects and write the note (6 min)
- [ ] ✱ Stretch: An incremental predicate: recompute only the month that changed

### Session 3: Window functions

#### [day1#s3] Window functions

*Session 3*

- Write a running total with a window frame
- Detect changes with LAG over an ordered partition
- Keep one row per group with ROW_NUMBER and QUALIFY

#### [day1#over-keeps-rows] GROUP BY collapses rows; a window keeps them and adds a value

*GROUP BY and OVER*

```sql
-- file: one row per day
SELECT order_date, sum(revenue)
FROM mart.fct_order_line
GROUP BY order_date
```

```sql
-- file: every line, with its day
SELECT order_id, revenue,
  sum(revenue) OVER (
    PARTITION BY order_date)
FROM mart.fct_order_line
```

One September week: 7 rows on the left, 1,228 on the right, each with its day's total beside it.

#### [day1#partition-order-frame] Partition says where it restarts, order says what "so far" means

*Three parts of OVER*

```sql
-- file: Lab 1.3 · step 2
sum(margin) OVER (
  PARTITION BY month              -- restart each month
  ORDER BY order_date             -- "so far" in date order
  ROWS BETWEEN UNBOUNDED PRECEDING
           AND CURRENT ROW)        -- the frame
```

The last day of each month equals finance's monthly margin: 5,413,128 riyals for August.

#### [day1#lag-price-changes] LAG compares each price with the one before it

*The previous row*

```sql
-- file: Lab 1.3 · step 3
lag(cost_piece_sar) OVER (
  PARTITION BY product_id ORDER BY valid_from) AS previous_cost
```

| Product | From | Previous | New | Change |
| --- | --- | --- | --- | --- |
| P-1004 | 13 Sep | 2.73 | 3.06 | +12.1% |
| P-1019 | 15 Aug | 14.51 | 16.24 | +11.9% |
| P-1016 | 22 Aug | 28.08 | 31.27 | +11.4% |

#### [day1#qualify-one-per-group] ROW_NUMBER and QUALIFY keep the first or last row of each group

*One row per group*

```sql
-- file: deduplicate or pick the latest
SELECT * FROM stg.orders
QUALIFY row_number() OVER (
  PARTITION BY customer_id ORDER BY created_at DESC) = 1
```

- The same pattern deduplicates the re-sent lines of Lab 1.2 and picks the latest change event on Day 2.
- Windows run after WHERE, so WHERE cannot filter them; QUALIFY can.

#### [day1#incremental-predicates] Recompute only the month that changed

*Incremental predicates*

- **17,665** lines read by a full recompute
- **6,075** lines read for October alone

A predicate on the partition you know changed (`order_date >= DATE '2026-10-01'`) turns a rebuild into an update. The result must equal the full recompute: test that.

#### [day1#checkpoint-3] A running total that never resets

*Checkpoint*

**Question:** Your margin-to-date keeps growing across August, September and October instead of restarting on the first of each month. What is missing?

- A. PARTITION BY month in the window
- B. ORDER BY month instead of order_date
- C. A GROUP BY month around the query
- D. ROWS BETWEEN 30 PRECEDING AND CURRENT ROW

#### [day1#lab-1-3] Running margin, price changes, first and last orders

Lab 1.3 · 25 min

Compute the running margin by month, each supplier price change with its size, and every customer's first and last order.

[D1_3_windows.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D1_3_windows.ipynb)

- [ ] GROUP BY against OVER on one week (4 min)
- [ ] Running margin that restarts each month (6 min)
- [ ] Supplier price changes with LAG (7 min)
- [ ] First and last order per customer (8 min)
- [ ] ✱ Stretch: ROW_NUMBER, RANK and DENSE_RANK on a tie

### Session 4: Columnar files and partitioning

#### [day1#s4] Columnar files and partitioning

*Session 4*

- Convert row files to Parquet and compare size and scan time
- Read row-group statistics and see which groups a filter skips
- Partition by month and measure what a one-month query reads

#### [day1#parquet-vs-csv] The same lines as Parquet are seven times smaller and scan 25 times faster

*Lab 1.4 · full run, 745,200 lines*

| Item | Value |
| --- | --- |
| CSV size | 71.1 MB |
| Parquet size | 9.6 MB |
| CSV scan | 545 ms |
| Parquet scan | 21 ms |

#### [day1#row-group-statistics] Each row group keeps the minimum and maximum of every column

*Inside a Parquet file*

- A reader checks the footer first and skips the row groups whose range cannot match the filter.
- Shuffled rows: every group spans every date, so nothing is skipped.
- Sorted rows: each group covers a few days.

| Rows | Groups that may hold 14 Sep |
| --- | --- |
| shuffled | 7 of 7 |
| sorted by date | 2 of 15 |

#### [day1#hive-partitions] A folder per month lets the reader skip whole files

*Partitioning*

```sql
-- file: Lab 1.4 · step 3
COPY big TO 'by_month' (FORMAT parquet, PARTITION_BY (month));
-- by_month/month=2026-08/…  month=2026-09/…  month=2026-10/…
SELECT … FROM read_parquet('by_month/*/*.parquet', hive_partitioning = true)
WHERE month = '2026-09'      -- Scanning Files: 1/3
```

The September query reads 2.8 MB of 9.6 MB. At this size the time hardly changes; on object storage the bytes are the bill.

#### [day1#too-many-small-files] Partition by day and customer and a full scan is 180 times slower

*The opposite mistake*

- **3,841** files, most under a kilobyte
- **15 ms → 2,725 ms** one file against all of them

Every file has a footer to open and a request to make. Partition on a column that queries filter by and that has few values.

#### [day1#checkpoint-4] The query that reads everything

*Checkpoint*

**Question:** The lines are partitioned by month, yet a query for September still scans all three folders. The filter is `WHERE strftime(order_date, '%Y-%m') = '2026-09'`. Why?

- A. Parquet cannot prune folders
- B. The row groups are not sorted
- C. Three folders are too few to prune
- D. The filter is on order_date, not on the partition column month

#### [day1#lab-1-4] Partitioned columnar files, measured

Lab 1.4 · 25 min

Convert the order-line extracts to Parquet partitioned by month, and measure query time and bytes read against the CSV.

[D1_4_columnar.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D1_4_columnar.ipynb)

- [ ] CSV against Parquet: size and scan time (6 min)
- [ ] Row groups and their statistics (6 min)
- [ ] Partition by month and query one month (8 min)
- [ ] Too many small files, measured (5 min)
- [ ] ✱ Stretch: Prove the pruning in the query plan

#### [day1#day-1-recap] Three things to keep from today

*Day 1*

- **Match the store to the question.** Rows for lookups by key, columns for scans. Analytics runs on a copy.
- **Reproduce before you trust.** Count against keys, join on the valid price, and match a reference to the riyal.
- **Lay files out for the reads.** Parquet, sorted, partitioned by what queries filter on, not too small.

#### [day1#tomorrow-ingest] Tomorrow the data stops arriving as tidy extracts

*Day 2 · Ingest and clean*

- A paginated supplier price API that throttles you and re-sends corrections
- A change feed with duplicates, events out of order and a deleted supplier
- Prices in three currencies, per carton or per piece, with Arabic names spelt four ways

Before tomorrow: make sure `uv run python -c "import dlt, polars"` works, or open Lab 2.1 in Colab once.

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

## Day 3: Model and test

#### [day3#title] Model and test

*SDAIA Academy · Modern Data Engineering*

Day 3

AI Engineering Track · 4 teaching days + capstone day · 4 sessions · 4 labs · AE-306

#### [day3#agenda] Model and test

*Today*

- **Session 1 · Dimensional modelling**: State the grain, then facts and dimensions that answer finance's questions
- **Session 2 · Transformations as code**: SQL models in git, environments, and plans that rebuild only what changed
- **Session 3 · Data quality tests and contracts**: Tests on data, a contract with the producer, and a gate that holds when the feed breaks
- **Session 4 · Orchestration**: Assets with dependencies, partitions, retries, blocking checks and backfills

#### [day3#review-day-2] A supplier moves country

*Review of Day 2*

**Question:** Jumeirah Canning moved from the UAE to Saudi Arabia on 1 September. Finance asks for August's margin by supplier country. Which supplier table gives the right answer?

- A. The type 2 history, joined on the order's creation time
- B. The merged copy of the supplier table
- C. The snapshot of 1 August
- D. The change feed itself

### Session 1: Dimensional modelling

#### [day3#s1] Dimensional modelling

*Session 1*

- State the grain of a fact table in one sentence and test it
- Build dimensions with an unknown member and a type 2 supplier
- Find and fix a fan-out before it reaches a report

#### [day3#five-finance-questions] Finance asks five questions of the margin every month

*Start from the questions*

| # | Question | Needs |
| --- | --- | --- |
| 1 | Revenue, cost and margin by month | a date |
| 2 | By customer type and city | the customer |
| 3 | By supplier country at the time of the order | the supplier version |
| 4 | By category and month | the product |
| 5 | By city after freight | freight, counted once |

#### [day3#grain-first] State the grain in one sentence before anything else

*Dimensional modelling*

- **Qafila's grain.** One row per line of a confirmed order.

- Facts are the numbers that add up at that grain: pieces, revenue, cost, freight.
- Dimensions are what you group and filter by: date, customer, product, supplier.
- A fact at another grain (freight per shipment) must be brought to this one, or get its own table.

#### [day3#margin-star] One fact table, four dimensions around it

*Lab 3.1 · step 1*

- **dim_customer.** type, city; plus an unknown member
- **fct_order_line.** order_id, line_no, order_date, customer_id, product_id, supplier_key; qty_pieces, revenue, cost, freight
- **dim_product.** category, units per carton

- **dim_supplier (type 2).** one row per version: country valid from, valid to
- **date.** order_date, and the month derived from it

#### [day3#unknown-member] An unknown member keeps revenue that has lost its customer

*The erased customer*

- C-1187 asked to be erased: the customer row is gone, 13 orders remain.
- An inner join drops their 139,619 riyals from some reports and not others.
- A row `'Unknown'` in the dimension, and the fact points to it: every report shows the same total, with the unknown visible.

#### [day3#freight-fan-out] Join freight per shipment to lines and it is counted 3.9 times

*Lab 3.1 · step 3*

- **772,575** riyals of freight billed
- **3,036,762** after joining it to order lines

Fix: share each shipment's freight among its lines by a stated rule (here, revenue share), or keep a shipment fact at its own grain.

#### [day3#five-answers-match] All five answers match finance's key, and question 5 changes the ranking

*Lab 3.1 · step 4*

| City | Margin | Freight | After freight |
| --- | --- | --- | --- |
| Jeddah | 5,795,845 | 220,754 | 5,575,091 |
| Dammam | 5,547,067 | 338,597 | 5,208,470 |
| Riyadh | 3,830,144 | 211,589 | 3,618,555 |

Largest difference from the key on any of the five questions: 0.10 riyal, from rounding.

#### [day3#checkpoint-1] Where does freight go?

*Checkpoint*

**Question:** Freight is charged per shipment, one shipment per order, and finance wants margin after freight by product category. What do you add to the star?

- A. Join shipments to the fact in each report
- B. Freight as an attribute of the customer
- C. A freight fact on the line, allocated by a stated rule
- D. One freight total per month, outside the star

#### [day3#lab-3-1] The margin star schema

Lab 3.1 · 25 min

Draw the margin star schema at order-line grain, build it, and check it against the finance team's five margin questions.

[D3_1_star_schema.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D3_1_star_schema.ipynb)

- [ ] Draw the star: grain, facts, dimensions (6 min)
- [ ] Dimensions with an unknown member (5 min)
- [ ] The fact table, and a grain test (6 min)
- [ ] Five finance questions against the key (8 min)
- [ ] ✱ Stretch: Allocate freight by pieces instead of revenue: which answers move?

### Session 2: Transformations as code

#### [day3#s2] Transformations as code

*Session 2*

- Write staging and mart models as SQL files under version control
- Plan a change in a development environment before production
- Show that a rebuild skips unchanged models

#### [day3#models-as-files] One SQL file per model, in git; the dependencies come from the SQL

*Transformations as code*

```sql
-- file: models/stg_order_lines.sql
MODEL (name stg.order_lines, kind FULL, grain (order_id, line_no));

-- the nightly extract re-sent one day's lines: keep one copy of each line
SELECT CAST(order_id AS BIGINT) AS order_id, CAST(line_no AS INTEGER) AS line_no, …
FROM raw.order_lines
QUALIFY row_number() OVER (PARTITION BY order_id, line_no) = 1
```

Eleven models: six staging, four mart tables, one monthly mart. A review is a diff; a rollback is a revert.

#### [day3#dev-and-prod] Build in dev; promoting to prod moves no data

*Lab 3.2 · step 3*

**plan dev** 11 models built → **check** margin equals the key → **plan prod** 0 models built

Production's views were pointed at the tables dev had built: same model versions, same tables. A virtual environment costs a view per model.

#### [day3#state-aware-rebuild] A change rebuilds what it reaches, and skips the rest

*Lab 3.2 · step 4*

| Change | Kind | Rebuilt | Skipped |
| --- | --- | --- | --- |
| New column in stg_products | non-breaking | 1 | 10 |
| Filter rows in stg_orders | breaking | 3: stg.orders, fct_order_line, margin_monthly | 8 |

#### [day3#verify-agent-sql] A model an assistant wrote runs, has the right grain, and is wrong by 51 million

*Verifying agent-written SQL*

- **116,950,038** revenue of the agent's "margin by product"
- **65,500,535** revenue of the tested mart

Three defects: prices joined without dates, cancelled orders kept, the discount missing. The grain test passes; the reconciliation fails.

#### [day3#checkpoint-2] What rebuilds?

*Checkpoint*

**Question:** You change the rows `stg.orders` returns. Qafila's project has eleven models. Which ones does a state-aware plan rebuild?

- A. All eleven
- B. stg.orders and the models downstream of it
- C. stg.orders only
- D. stg.orders and the raw tables it reads

#### [day3#lab-3-2] Models, environments and a state-aware rebuild

Lab 3.2 · 25 min

Build Qafila's staging and mart models as version-controlled SQL with SQLMesh, plan them in dev and prod, and show that a change rebuilds only what depends on it.

[D3_2_transformations.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D3_2_transformations.ipynb)

- [ ] The project and its first commit (5 min)
- [ ] Write the mart model (6 min)
- [ ] Plan dev, then promote to prod (6 min)
- [ ] Change one model: what rebuilds? (8 min)
- [ ] ✱ Stretch: Review an agent-written model: run it against your tests before you trust it

### Session 3: Data quality tests and contracts

#### [day3#s3] Data quality tests and contracts

*Session 3*

- Write not-null, unique, accepted-value and relationship tests
- Write a data contract for a feed and compile it to SQL checks
- Block a refresh when the contract fails, and say why

#### [day3#four-test-kinds] Four kinds of test cover most of a staging table

*Tests on data*

- **Not null.** every price has an id
- **Unique.** one row per price id
- **Accepted values.** SAR, USD or AED
- **Relationships.** every product exists

A test is a query returning the rows that break a rule: zero rows passes. One negative cost inserted on purpose trips both the unique and the positive-cost tests.

#### [day3#data-contract-odcs] The producer and the consumer agree on the feed, in a file both can read

*A data contract*

```yaml
# file: contracts/supplier_prices.odcs.yaml
apiVersion: v3.1.0
kind: DataContract
id: qafila-supplier-prices
schema:
  - name: supplier_prices
    properties:
      - name: cost
        logicalType: string
        required: true
        quality:
          - id: cost_positive_number
            type: sql
            query: SELECT count(*) FROM {object} WHERE num({property}) <= 0
            mustBe: 0
```

#### [day3#contract-to-sql] Each rule compiles to one query that returns one number

*Lab 3.3 · step 3*

| Rule | Compiled SQL |
| --- | --- |
| `nullValues` | `SELECT count(*) FROM t WHERE price_id IS NULL` |
| `duplicateValues` | `SELECT count(*) - count(DISTINCT (price_id, updated_at)) FROM t` |
| `invalidValues` | `… WHERE currency NOT IN ('SAR', 'USD', 'AED')` |
| `required` | the column exists in the batch |

Seven quality rules and nine required columns: sixteen checks, all passing on the October feed.

#### [day3#gate-holds] The November batch breaks the contract and the price table does not move

*Lab 3.3 · step 4*

- `cost` renamed to `unit_cost`: `cost_present` fails
- The cost rule cannot run: it fails too
- Hidden behind them: a negative cost, -135.30 on PR-00043
- The fixed batch passes and the refresh runs

- **What the margin reads.** 102 prices before, 102 after the broken batch, unchanged to the halala. October's prices stay until the fix.

#### [day3#checkpoint-3] The night run

*Checkpoint*

**Question:** The contract fails on a renamed column during the night run, and finance opens the margin report in the morning. What should they find?

- A. A margin computed from whatever columns matched
- B. An empty report until the feed is fixed
- C. A margin with unit_cost mapped to cost automatically
- D. Yesterday's margin, labelled with its last refresh

#### [day3#lab-3-3] A contract that holds

Lab 3.3 · 25 min

Write tests and an ODCS contract for the supplier feed, compile the contract to SQL checks, break the feed on purpose and watch the gate keep the mart unchanged.

[D3_3_contracts.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D3_3_contracts.ipynb)

- [ ] Tests on the staged prices (6 min)
- [ ] The contract in YAML (6 min)
- [ ] Compile the contract to SQL checks (6 min)
- [ ] Break the feed: the gate holds (7 min)
- [ ] ✱ Stretch: Quarantine the failing rows instead of blocking: when is that right?

### Session 4: Orchestration

#### [day3#s4] Orchestration

*Session 4*

- Declare the pipeline as assets with dependencies and monthly partitions
- Retry a flaky source and block on a failed check
- Backfill one month after a fix

#### [day3#assets-graph] Declare the tables and what they depend on; the graph follows

*Orchestration*

1. **supplier_prices** retry 3 times
2. **november_batch** contract check, blocking
3. **current_prices**
4. **fct_order_line**
5. **margin_monthly** by month

#### [day3#retry-or-block] Retry the transport; block on the data

*Lab 3.4 · steps 2 and 3*

- **Retried: the API answers 503 twice.** `RetryPolicy(max_retries=3, delay=0.2)`. Two failures, two retries, 127 versions loaded.
- **Blocked: the contract fails.** `blocking=True`. current_prices and fct_order_line: "Not executing".

A second try can fix a timeout. It cannot fix a renamed column.

#### [day3#partitions-backfill] Partition the margin by month and a backfill touches one month

*Lab 3.4 · step 4*

| Month | Margin | Built by run |
| --- | --- | --- |
| 2026-08 | 5,413,128 | the first month's run |
| 2026-09 | 4,807,938 | the second month's run |
| 2026-10 | 4,985,708 | **the backfill** |

The backfill rebuilt October only; August and September keep the runs that built them.

#### [day3#lineage-events] Every run can say what it read and what it wrote

*Lineage*

```json
// file: one OpenLineage-style event
{"eventType": "COMPLETE",
 "run": {"runId": "6e655101-…"},
 "job": {"namespace": "qafila", "name": "fct_order_line"},
 "inputs": [{"namespace": "qafila", "name": "current_prices"}],
 "outputs": [{"namespace": "qafila", "name": "fct_order_line"}]}
```

Lineage answers the auditor's question: which run, from which inputs, produced the number on the report.

#### [day3#checkpoint-4] Retry or block?

*Checkpoint*

**Question:** Four failures in last week's runs. Which one should a retry policy handle?

- A. The supplier API timed out after 30 seconds
- B. The contract found a negative cost
- C. A model divides by a column that was renamed
- D. The warehouse disk is full

#### [day3#lab-3-4] Assets, a failure, a retry and a backfill

Lab 3.4 · 25 min

Declare the pipeline as Dagster assets on a nightly schedule, watch a retry absorb a flaky API, let the contract check block the mart, fix the feed and backfill one month.

[D3_4_orchestration.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D3_4_orchestration.ipynb)

- [ ] Assets, their graph and a schedule (6 min)
- [ ] A flaky source and a retry policy (5 min)
- [ ] The broken feed: the check blocks the mart (7 min)
- [ ] Fix, then backfill one month (7 min)
- [ ] ✱ Stretch: Emit lineage events for each run

#### [day3#day-3-recap] Three things to keep from today

*Day 3*

- **Grain, then the star.** One sentence, tested; facts at that grain; unknown members; history by version.
- **Models with state.** Files in git, environments, rebuilds that reach only what changed.
- **Fail safely.** A contract with an owner, a blocking check, retries for the transport, backfills by partition.

#### [day3#tomorrow-scale] Tomorrow the mart leaves DuckDB's file and becomes an open table

*Day 4 · Scale and production*

- An Iceberg table that a second engine reads, at today's snapshot and at last week's
- When a distributed engine pays, measured on a laptop
- Shipment events that arrive late, and the classification of every field Qafila holds

Before tomorrow: run `uv run python -c "import pyiceberg, dask"`, or open Lab 4.1 in Colab once.

## Day 4: Scale and production

#### [day4#title] Scale and production

*SDAIA Academy · Modern Data Engineering*

Day 4

AI Engineering Track · 4 teaching days + capstone day · 4 sessions · 4 labs · AE-306

#### [day4#agenda] Scale and production

*Today*

- **Session 1 · Open table formats**: Snapshots, schema evolution, partition specs and time travel, read by more than one engine
- **Session 2 · Distributed processing when measured**: Partitions, shuffles and stages, and the measurement that decides whether you need them
- **Session 3 · Streaming fundamentals**: Logs, offsets, delivery guarantees, event time, windows and watermarks, reconciled with batch
- **Session 4 · Governance with PDPL and NDMO**: Classification levels, minimisation, masking and access rules, and erasure against history

#### [day4#review-day-3] The run that half failed

*Review of Day 3*

**Question:** Last night the supplier API timed out twice and then answered, and the contract check failed on the November batch. What should the run log show?

- A. The supplier load failed; nothing else ran
- B. Everything refreshed, with two warnings
- C. The load succeeded after retries; the check failed; the prices and the mart were not refreshed
- D. The check was retried three times and then skipped

### Session 1: Open table formats

#### [day4#s1] Open table formats

*Session 1*

- Write a table in an open format with a partition spec
- Evolve its schema without rewriting data
- Query an earlier snapshot from a second engine

#### [day4#why-table-format] A folder of Parquet files is not a table

*Open table formats*

| A table needs | Files alone | A table format adds |
| --- | --- | --- |
| Atomic writes | a reader can see half a write | a new snapshot appears in one commit |
| A schema that changes | old files disagree with new | columns tracked by id |
| Partitions | folder names, filter by hand | a partition spec, hidden from queries |
| History | overwritten | snapshots you can query by id |

#### [day4#iceberg-metadata-layers] Catalogue, metadata, manifests, data files: a reader walks down

*Lab 4.1 · step 2*

1. **Catalogue** points to the current metadata file
2. **metadata.json** schema, partition spec, snapshots
3. **Manifests** data files with column statistics
4. **Parquet** one file per month here

The lab's catalogue is a SQLite file; in production a REST catalogue (Polaris, Nessie, Glue and others) holds the pointer.

#### [day4#hidden-partitioning] Partition by month of the order date; filter on the date

*Lab 4.1 · step 1*

```python
# file: PyIceberg
table = catalog.create_table("mart.margin_lines", schema=lines.schema)
with table.update_spec() as spec:
    spec.add_field("order_date", MonthTransform(), "order_month")
table.append(august_and_september)          # 11,590 lines, 2 files
```

A query on `order_date` prunes months without naming a partition column: the fix for Day 1's checkpoint about the filter that read every folder.

#### [day4#schema-evolution-ids] Add freight in October: a metadata change, not a rewrite

*Lab 4.1 · step 3*

- The new column gets the next id (14); August's files have no column 14 and read it as null.
- The lab checks that every data file of the first snapshot is still there, unchanged.
- A rename changes the name, not the id: old files keep reading correctly.

- **Two snapshots.** The first: August and September. The current: three months with freight.

#### [day4#two-engines-same-answer] PyIceberg and DuckDB give identical answers at both snapshots

*Lab 4.1 · step 4*

| Margin (SAR) | PyIceberg | DuckDB |
| --- | --- | --- |
| Current, 2026-10 | 4,985,707.94 | 4,985,707.94 |
| Current, 2026-08 | 5,413,127.73 | 5,413,127.73 |
| First snapshot | 2 months, no October | 2 months, no October |

```sql
-- file: DuckDB
SELECT … FROM iceberg_scan('…/metadata/00002-….metadata.json',
                           snapshot_from_id = 8043377048285445159)
```

#### [day4#deletes-compaction-expiry] A deleted row stays in its file until maintenance removes it

*Deletes and maintenance*

| Operation | What it writes | What it leaves behind |
| --- | --- | --- |
| Delete or update a row | a rewritten data file, or a **deletion vector** marking the row's position | the old file, still read by earlier snapshots |
| Many small appends | many small data files | slow scans: Day 1's small-files problem |
| **Compaction** | fewer, larger files with the deletes applied | the replaced files, until they expire |
| Expire snapshots | shorter history | nothing: files no snapshot needs are deleted |

Maintenance is scheduled like any other asset. Until it runs, "deleted" means "hidden from the current snapshot".

#### [day4#checkpoint-1] The rename

*Checkpoint*

**Question:** An analyst renames `cost` to `unit_cost` in the Iceberg margin table. What happens to the Parquet files written in August?

- A. They are rewritten with the new name
- B. Nothing: they are read by column id under the new name
- C. They read the column as null from now on
- D. They are dropped with the old snapshots

#### [day4#lab-4-1] The mart as an Iceberg table

Lab 4.1 · 25 min

Write the margin mart to an Iceberg table partitioned by month, add a column, append a month, and read the current and an earlier snapshot from DuckDB with identical results.

[D4_1_table_format.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D4_1_table_format.ipynb)

- [ ] Create the table and its partition spec (6 min)
- [ ] Walk the metadata on disk (4 min)
- [ ] Evolve the schema and append (6 min)
- [ ] Two engines, two snapshots (9 min)
- [ ] ✱ Stretch: Expire old snapshots and see which files go

### Session 2: Distributed processing when measured

#### [day4#s2] Distributed processing when measured

*Session 2*

- Explain partitions, shuffles and stages in a distributed engine
- Run the same transformation on a local cluster and a single node
- Decide from measured time and memory, not from habit

#### [day4#partitions-shuffles-stages] Partitions, shuffles and stages

*Distributed processing*

- **Partitions.** The data split into pieces that workers process in parallel.
- **Shuffle.** Rows move between workers so equal keys meet: for joins and group-bys. The expensive step.
- **Stages.** The work between two shuffles; a stage ends where data must move.

#### [day4#broadcast-join] A small table is broadcast, so the join needs no shuffle

*Lab 4.2 · step 3*

```
# file: Dask's optimised plan
Sum(TreeReduce)
  Sum(GroupByChunk)
    Filter: valid_from <= order_date <= valid_to
      BlockwiseMerge: on product_id
        FromPandas  npartitions=8   (the lines)
        FromPandas  npartitions=1   (102 prices)
```

Each partition of lines meets the whole price list where it is; the month sums combine in a tree.

#### [day4#one-node-wins] At a million lines, one node is 160 times faster and uses a 27th of the memory

*Lab 4.2 · full run*

| Lines | DuckDB, one node | Dask, local cluster |
| --- | --- | --- |
| 176,650 | 0.13 s | 5.8 s |
| 1,059,900 | 0.16 s, 9 MB | 26.7 s, 243 MB |
| 4,239,600 | 0.51 s | 95.8 s |

The cluster never caught up on a 32 GB laptop. Same answer from both, to the riyal.

#### [day4#when-a-cluster] Choose a cluster when one machine cannot hold the work, not before

*The decision*

- The data, with the working space of the query, no longer fits one machine's memory and disk.
- A deadline that one machine cannot meet, shown by a measurement.
- Many independent jobs at once, where the cluster is shared.

> **Qafila:** three months of lines are a few megabytes. Ten years would be under a gigabyte. One node.

#### [day4#checkpoint-2] Which engine?

*Checkpoint*

**Question:** Your largest table is 3 GB of order lines and your laptop has 16 GB of memory. A colleague proposes a Spark cluster for the nightly margin. What do you answer?

- A. Yes: Spark is the standard for data engineering
- B. Yes, once the table passes 4 GB
- C. Wait until finance complains about speed
- D. One node, and measure again when the data grows

#### [day4#lab-4-2] One node or a local cluster

Lab 4.2 · 25 min

Run the heaviest transformation, the as-of margin join, on Dask in local cluster mode and on DuckDB, and compare run time and peak memory at two data sizes.

[D4_2_distributed.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D4_2_distributed.ipynb)

- [ ] The heaviest transformation on one node (5 min)
- [ ] The same on a local cluster (8 min)
- [ ] Read the task graph: where is the shuffle? (5 min)
- [ ] Time and memory at two sizes (7 min)
- [ ] ✱ Stretch: Find the size at which the cluster wins on your laptop

### Session 3: Streaming fundamentals

#### [day4#s3] Streaming fundamentals

*Session 3*

- Consume a log by offset and commit progress
- Make a consumer idempotent under at-least-once delivery
- Window by event time with a watermark and reconcile with batch

#### [day4#log-offsets-groups] A log, offsets and consumer groups

*Streaming fundamentals*

- Producers append events; each gets the next **offset**.
- A consumer group commits the offset it will read next, so a restart resumes there.
- Several groups read the same log independently: operations and finance each have their own position.

- **Lab 4.3.** 2,312 shipment events, one partition, read in batches of 100, committed after each batch.

#### [day4#at-least-once] A crash before the commit replays the batch: count by key, not by event

*Lab 4.3 · step 2*

- **747** deliveries, counting events
- **709** deliveries, by shipment id

The consumer crashed at offset 1,049 with its last commit at 1,000, and the carriers sent 55 events twice. Keyed by shipment, the replay changes nothing.

#### [day4#event-time-watermark] Window by when it happened; close the window when the watermark passes

*Event time*

1. **Event time** delivered on 21 October
2. **Watermark** latest event time minus allowed lateness
3. **Window closes** 21 October emitted
4. **Late event** dropped and logged

#### [day4#watermark-tradeoff] A longer watermark answers later and drops less

*Lab 4.3 · step 4 and stretch*

| Item | Value |
| --- | --- |
| 1 hour | 22 dropped |
| 1 day | 9 dropped |
| 3 days | 0 dropped |

Every delivery the stream misses is a late event the watermark dropped; the daily batch recount (709 deliveries) repairs it.

#### [day4#checkpoint-3] One hour or one day?

*Checkpoint*

**Question:** Operations wants yesterday's deliveries on the screen each morning; finance closes the month from the batch. Which watermark fits operations?

- A. Short, with the late events logged and the batch reconciling
- B. Three days, so nothing is ever dropped
- C. No watermark: count events as they arrive
- D. Replace the stream with the nightly batch

#### [day4#lab-4-3] Shipment events with a watermark

Lab 4.3 · 25 min

Consume shipment events from a local single-broker log, survive a crash without double counting, handle late arrivals with a watermark and reconcile daily deliveries with the batch result.

[D4_3_streaming.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D4_3_streaming.ipynb)

- [ ] Produce and consume by offset (5 min)
- [ ] Crash, replay and count once (7 min)
- [ ] Daily windows with a watermark (8 min)
- [ ] Reconcile with the batch result (5 min)
- [ ] ✱ Stretch: Two watermarks: what each one drops and how late it answers

### Session 4: Governance with PDPL and NDMO

#### [day4#s4] Governance with PDPL and NDMO

*Session 4*

- Classify every field under the national classification levels
- Drop what the report does not need and mask the rest per role
- Test that a role cannot read what it must not

#### [day4#national-classification-levels] Four levels, by the impact of unauthorised disclosure

*National Data Classification Policy*

| Level | Impact | Examples the policy gives |
| --- | --- | --- |
| Top Secret | high | national security, critical infrastructure keys |
| Secret | medium | vital installations, major financial loss |
| Restricted (older texts: Confidential) | low | personally identifiable information, bank accounts, supplier contracts and quotations |
| Public | none | public announcements, contact persons at organisations |

#### [day4#classification-register] Twenty fields: twelve Restricted, eight Public, four personal

*Lab 4.4 · step 1*

| Field | Level | Personal |
| --- | --- | --- |
| customers.mobile, email, contact_name | Restricted | yes |
| suppliers.contact_name | Restricted | yes |
| suppliers.iban, contract_ref, payment_terms_days | Restricted | no |
| suppliers.contact_email (sales@…) | Public | no |
| customers.city, customer_type | Public | no |

#### [day4#minimise-then-mask] Drop what the report does not need; mask what a role needs in part

*Lab 4.4 · steps 2 and 3*

- **Minimise.** The mart keeps customer_id, type and city. Seven customer fields never reach it.
- **Mask for the analyst.** `M. A.-Q.` · `+966*******86` · `***@riyadh-shop.example`

The Personal Data Protection Law asks for personal data to be limited to what the purpose needs. A field that is not there needs no mask and no test.

#### [day4#access-tests] Test the rules as code, on every build

*Lab 4.4 · step 4*

| Test on the analyst's connection | Result |
| --- | --- |
| The raw customer table cannot be read | pass |
| No value looks like a full Saudi mobile number | pass |
| No value is a full e-mail address | pass |
| Margin by city still matches finance's question 5 | pass |

The same tests fail on the finance controller's connection, as they should.

#### [day4#erasure-reaches-history] Erasure must reach every copy, not only the current table

*The erased customer*

- C-1187's row is gone from the customer table; 13 orders stay with the unknown member.
- Last quarter's customer snapshot still holds the contact name, mobile and e-mail.
- Table formats keep old snapshots: expire them, and delete the files they leave.

#### [day4#ndmo-quality-architecture] The pipeline already writes the evidence a quality and architecture audit asks for

*NDMO Data Management and Personal Data Protection Standards*

| Area of control | What an auditor asks | Evidence from this week |
| --- | --- | --- |
| Data quality | Which rules, and who owns them? | the contract and its owner (Lab 3.3) |
| What happened when a rule failed? | the run log of the blocked batch (Lab 3.4) |  |
| Architecture and modelling | Where is the model, and who changed it? | the star and the models in git (Labs 3.1, 3.2) |
| Where did this number come from? | lineage events per run (Lab 3.4) |  |
| Personal data | Who may read each field? | the register and access tests (Lab 4.4) |

#### [day4#checkpoint-4] Still in last month's snapshot

*Checkpoint*

**Question:** A customer asked to be erased. The row is gone from today's table, but last month's Iceberg snapshot still holds the contact data. What removes it?

- A. A masked view on the current table
- B. Moving the snapshot to cheaper storage
- C. Expire the snapshots that hold it and delete their files
- D. Reclassifying the old snapshot as Restricted

#### [day4#lab-4-4] Classification, masking and access tests

Lab 4.4 · 25 min

Classify every customer and supplier field, drop what the margin report does not need, mask customer contact data for the analyst role, and test that the role cannot read it.

[D4_4_governance.ipynb](https://sdaiaacademy.github.io/ae-306/labs/D4_4_governance.ipynb)

- [ ] The classification register (7 min)
- [ ] Minimise: drop what the report does not need (4 min)
- [ ] Masked views per role (7 min)
- [ ] Access tests for the analyst role (7 min)
- [ ] ✱ Stretch: Trace an erased customer through history and snapshots

#### [day4#day-4-recap] Three things to keep from today

*Day 4*

- **Open tables.** Snapshots, ids, hidden partitions: two engines, one answer, any point in time.
- **Measure before you scale.** One node until a measurement says otherwise; know your shuffles.
- **People in the data.** Classify every field, minimise, mask per role, test access, erase every copy.

#### [day4#tomorrow-capstone] Tomorrow you build Qafila's margin mart from raw sources to an Iceberg table

*Day 5 · Capstone*

- Start from `labs/capstone/`: the starter, the contract, the reference models
- The assessor re-runs your pipeline from a clean checkout
- An eight-minute defence of one modelling decision

Before tomorrow: create an empty public GitHub repository for your submission and read `labs/capstone/README.md`.

## Capstone: Capstone: the margin mart and its defence

#### [day5#title] Capstone: the margin mart and its defence

*SDAIA Academy · Modern Data Engineering*

Capstone

AI Engineering Track · 4 teaching days + capstone day · 8 min talk and demo · AE-306

#### [day5#agenda] How the day runs

*Capstone*

- **The brief, the rubric and the last build**: what the assessor re-runs, then the morning to finish
- **Defences**: eight minutes each, with questions after
- **Review and closing**: the trainer's review, the follow-up task

#### [day5#the-brief] Qafila's margin mart, from the raw extracts to an Iceberg table

*What you build*

- **Ingest** the API and the change feed; supplier history as type 2.
- **Model** a star at order-line grain, cost as of the order date.
- **Test** and reconcile with finance's five answers.

- **Gate** each batch with the contract: a broken one changes nothing.
- **Store** the mart as Iceberg, read by a second engine.
- **Govern** the fields: register, masking, access tests.

> **Starter:** `labs/capstone/pipeline.py` has the nine steps, each naming the lab it reuses. The first is done.

#### [day5#rerun] The assessor clones your repository and runs it from nothing

*Reproducibility*

```
git clone <your repository>
# then the commands of your README; with the starter:
cd <it>/labs && uv sync
uv run python capstone/pipeline.py
uv run python capstone/pipeline.py --batch broken
uv run python capstone/pipeline.py --backfill 2026-10
```

| Run | Must show |
| --- | --- |
| Fixed batch | row counts and test results equal to your README |
| Broken batch | the contract's failed checks, and the mart not refreshed |
| Second run | no new rows from the API |
| Backfill | one month rebuilt, the others untouched |

> **Clone it yourself first,** into a new folder. A file only on your laptop fails the run.

#### [day5#rubric] The rubric

*How the repository is scored*

| Item | Value |
| --- | --- |
| Correctness of the mart | 25% |
| Ingestion and history | 20% |
| Tests and contract | 20% |
| Orchestration and recovery | 15% |
| Table format and governance | 10% |
| Reproducibility | 10% |

> **The repository is 60% of your result** and needs at least 60% on this rubric. The defence is 20%, the supervised checks 20%. The pass mark is 70% overall.

#### [day5#defence-format] Eight minutes for each defence

*Format*

- **3 · One modelling decision.** What you chose, the alternative, and the number that shows you were right.
- **3 · A transformation we pick.** What it reads, what it writes, and what would break it.
- **2 · The broken batch.** The run log: what was caught, what stayed in place.

> **AI-full.** Coding agents were allowed. Explaining what they wrote is part of the defence.

#### [day5#running-order] Who defends when

*Running order*

| # | Participant | Transformation selected |
| --- | --- | --- |
| 1 |  |  |
| 2 |  |  |
| 3 |  |  |
| 4 |  |  |
| 5 |  |  |
| 6 |  |  |
| 7 |  |  |
| 8 |  |  |

#### [day5#final-prep] Final prep · 20 minutes

*Before the first defence*

Clone your repository into a new folder and run it twice.

#### [day5#now-presenting] Defence

*Now defending*

#### [day5#review] What the defences showed

*Trainer review*

- **Strongest patterns.** What several marts got right.
- **Common gaps.** What most would fix next.
- **One surprise.** Something nobody expected.

#### [day5#what-next] The follow-up task, and the AE Associate badge

*What next*

- **Follow-up task.** Within four weeks, put one contract gate in front of a feed at work and report what it caught.
- **Keep the repository.** It is the evidence the AE Associate badge looks at.

#### [day5#thanks] Thank you

*SDAIA Academy*

Modern Data Engineering
