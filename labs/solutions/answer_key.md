# Answer key, for the trainer

The data is synthetic and generated with a fixed seed (`qafila_data.py`, seed 306), so these figures are the same on
every machine. Figures marked *full* come from a full run; in quick mode (`DE_QUICK=1`) the timing labs use fewer rows
and print smaller numbers, while every answer the labs check stays the same. Timings depend on the laptop: compare the
ratios, not the seconds.

## Planted problems

| # | Problem | Where it is found |
|---|---|---|
| 1 | `order_lines.csv` repeats every line of the orders placed on 14 September (a re-sent batch) | Lab 1.2 |
| 2 | The old margin report counts cancelled orders | Lab 1.2 |
| 3 | Order lines are priced per carton or per piece; cost is per piece | Lab 1.2 |
| 4 | Prices change inside the quarter: cost needs the price valid on the order date | Labs 1.2, 1.3 |
| 5 | Customer C-1187 asked to be erased: the customer row is gone, the orders stay | Labs 1.3, 3.1, 4.4 |
| 6 | The supplier API re-sends corrected prices with a later `updated_at`, and adds `incoterm` in October | Labs 2.1, 2.2 |
| 7 | API costs come per carton or per piece, in SAR, USD or AED, some with Arabic-Indic digits or a decimal comma; supplier names in several Arabic spellings | Lab 2.4 |
| 8 | The supplier change feed repeats events and delivers some out of order | Lab 2.3 |
| 9 | Supplier S-07 moves from the UAE to Saudi Arabia on 1 September; S-12 is deleted on 10 October | Labs 2.3, 3.1 |
| 10 | Freight is per shipment (one per order): joining it to lines repeats it | Lab 3.1 |
| 11 | The November supplier batch renames `cost` to `unit_cost` and carries a negative cost | Labs 3.3, 3.4 |
| 12 | Shipment events arrive late (some by days) and some twice | Lab 4.3 |

## Expected figures by lab

| Lab | What the participant should find |
|---|---|
| 1.1 | Ten workloads placed against `data/reference/workloads.json`. *Full:* a single-order lookup takes 0.04 ms in SQLite against 1.87 ms in DuckDB; a monthly aggregate 662 ms against 56 ms. |
| 1.2 | August revenue in the old report 23,219,590 SAR against finance's 22,305,918 (+4.1%). Cancelled orders add 913,673 in August; the re-sent lines add 901,432 in September (227 lines, all dated 14 September). The monthly margin matches finance within 0.011 SAR (one halala of rounding). |
| 1.3 | 44 price changes, 17 of them above 5%. Customer C-1187 is an orphan with 13 orders. |
| 1.4 | *Full (745,200 lines):* CSV 71.09 MB read in 545 ms, Parquet 9.62 MB in 21 ms. A one-date query may need 7 of 7 row groups unsorted, 2 of 15 sorted. The September partition is 2.84 MB. 3,841 small files take 2,725 ms against 15 ms for one file. |
| 2.1 | 99 price versions in 7 requests with one 429; a re-run adds 0; the next release adds 28 (3 new prices, 25 corrections). |
| 2.2 | 93 prices, then 102 after the October release; `incoterm` CIF 10, DAP 9, FOB 15, null 68. |
| 2.3 | 38 change events, 3 duplicates, 1 out of order; 19 suppliers; 52 versions, 19 current. No supplier has overlapping ranges. |
| 2.4 | 21 non-plain costs; 56 spellings map to 18 supplier ids; 102 prices reconcile within one halala. |
| 3.1 | Freight 772,575 SAR from shipments against 3,036,762 after the naive join (3.9 times). 17,665 fact rows. All five finance questions match within 0.10. Margin after freight by city: Jeddah 5,575,091, Dammam 5,208,470, Riyadh 3,618,555. |
| 3.2 | The dev environment builds 11 models while prod is untouched (0); a non-breaking change rebuilds 1, a breaking change 3. The agent-written SQL totals 116,950,038 against the reference 65,500,535: it joins prices without their dates, keeps cancelled orders and leaves the discount out. |
| 3.3 | The broken batch fails `cost_present` and `cost_positive_number`; the negative cost is on PR-00043; in the stretch, after mapping `unit_cost` back to `cost`, 36 rows are loadable and 1 is quarantined. The fixed batch passes every rule. In the second stretch, the 1.1.0 batch with both fields passes the 1.0.0 contract; 8 of 37 rows disagree (every cost written with the Arabic decimal separator, so unit_cost is 100 times cost); two consumers still read cost, so 2.0.0 waits. |
| 3.4 | The schedule `nightly_refresh_schedule` launches the job `nightly_refresh` (declared and inspected; no daemon runs in the notebook). The API asset succeeds after 2 retries and loads 127 versions; the blocked run leaves `current_prices` and the fact not executed; the backfill rebuilds October only. |
| 4.1 | 11,590 lines, then 6,075 appended; 2 data files; PyIceberg and DuckDB return identical results at both snapshots. |
| 4.2 | *Full:* 176,650 lines DuckDB 0.13 s against Dask 5.8 s; 1,059,900 lines 0.16 s and 9 MB against 26.7 s and 243 MB; 4,239,600 lines 0.51 s against 95.8 s. On one laptop the single node wins at every size. |
| 4.3 | A naive count of 747 deliveries against 709 when counted idempotently; 55 duplicate events. Late events dropped by the watermark: 22 at one hour, 9 at one day, 0 at three days. |
| 4.4 | 20 of 20 fields agree with `data/reference/classification.json` (12 Restricted, 8 Public, 4 personal); 4 access tests pass. C-1187 still appears in `customers_2026-09-30.csv`, the older extract: erasure must reach history and snapshots too. |

## Capstone reference

`solutions/capstone_pipeline.py` runs the whole mart in about 25 seconds on a laptop and passes 13 tests with the
fixed batch. With `--batch broken` it stops at the contract (`cost_present`, `cost_positive_number`) and does not
refresh the mart. With `--backfill 2026-10` after the fix it rebuilds October of the monthly mart only and adds a
fourteenth test, that the other months did not change. `_tools/make_capstone_starter.py` writes `capstone/pipeline.py` from it.

## Choices that a trainer may be asked about

- **Dask in local mode** stands in for Spark or Trino in Lab 4.2: Spark needs Java, which a Colab-or-laptop course
  cannot assume. The lesson, that one node wins at this size, is the same.
- **A file-backed log** stands in for a Kafka broker in Lab 4.3, for the same reason; offsets, consumer positions and
  watermarks behave as they would on a single-partition topic.
- **A separate DuckDB file per role** in Lab 4.4, because DuckDB has no users or grants.
- **Fixed exchange rates** (`RATES` in `qafila.py`): USD 3.75, AED 1.0211.
- **The supplier sales address** (`sales@...`) is classified Public as an organisation's contact point; the contact
  person's name stays Restricted. Expect debate: that is the point of the exercise.
