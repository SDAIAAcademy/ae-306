---
course: "Modern Data Engineering"
code: "AE-306"
version: "2027.1.0"
deck: "day1"
day: 1
language: "en"
view: "trainee"
source: "https://sdaiaacademy.github.io/ae-306/slides/day1.html"
---

# Modern Data Engineering

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
