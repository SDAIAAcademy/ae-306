---
course: "Modern Data Engineering"
code: "AE-306"
version: "2027.2.0"
deck: "day3"
day: 3
language: "en"
view: "trainee"
source: "https://sdaiaacademy.github.io/ae-306/slides/day3.html"
---

# Modern Data Engineering

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

A test returns the rows that break a rule: zero rows passes.

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

#### [day3#expand-migrate-contract] Expand, migrate, then contract: both fields live until the last consumer moves

*A rename that breaks no one*

1. **1.0.0** freight_sar only
2. **1.1.0 expand** add freight_cost; fill both; a rule says they agree
3. **Migrate** consumers move one at a time; freight_sar still filled
4. **2.0.0 contract** drop freight_sar

Adding a field breaks nobody, so it is a minor version. Removing one breaks whoever still reads it, so it waits, and it is a major version.

#### [day3#cutover-register] Can 2.0.0 drop freight_sar today?

*Read the register, then decide*

| Consumer of the shipment extract | Reads today |
| --- | --- |
| fct_order_line (freight allocation) | `freight_cost` |
| Carrier cost review | `freight_cost` |
| Monthly freight file for finance | `freight_sar` |

- **Parallel check, 14 days of 1.1.0.** 729 rows with both fields; 0 where they disagree.

> **Not yet.** The values agree, but one consumer still reads `freight_sar`. Move it, watch one full cycle of its own run, then ship 2.0.0. Both conditions, every time.

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
