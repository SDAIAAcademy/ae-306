# Changes

## 2027.2.0 (2026-11-24)

- Added: `expand-migrate-contract` and `cutover-register` (day 3, session 3), a rename made without breaking any consumer: expand with both fields, migrate consumers one at a time, contract only after the last one has moved, read from a register of consumers and a parallel check on the shipment extract.
- Added: a second stretch in Lab 3.3, the supplier feed's rename done with both fields until cutover, with its reference solution and checks.
- Added: a practice question on moving consumers through a column rename (`de-lo4-parallel-change`).
- Added: `labs/_tools/freight_cutover.py`, which computes the numbers of `cutover-register`.
- Added: the source "Parallel Change" (Danilo Sato).
- Tightened: `four-test-kinds` and the notes of `contract-to-sql` (day 3).
