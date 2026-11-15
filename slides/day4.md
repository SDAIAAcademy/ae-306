---
course: "Modern Data Engineering"
code: "AE-306"
version: "2027.1.0"
deck: "day4"
day: 4
language: "en"
view: "trainee"
source: "https://sdaiaacademy.github.io/ae-306/slides/day4.html"
---

# Modern Data Engineering

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
