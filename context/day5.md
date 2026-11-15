---
course: "Modern Data Engineering"
code: "AE-306"
version: "2027.1.0"
deck: "day5"
day: 5
language: "en"
view: "trainee"
source: "https://sdaiaacademy.github.io/ae-306/slides/day5.html"
---

# Modern Data Engineering

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
