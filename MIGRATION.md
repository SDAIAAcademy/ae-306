# Migration of data-engineering

This course was moved from the previous slide system by `academy migrate`. The inner markup of every slide is unchanged; each `<section>` tag got an `id`, section slides a session number, lab slides their lab id, and a slide drawn with coordinates or holding a layout of the course's own stylesheet that cannot reflow `data-read="scaled"`. Each deck keeps its old file name as its unit id, so its published address keeps answering. `labs/` and `assets/` are copied as they were.

Run the engine from this folder with `node academy.mjs <command>` (`check`, `build`, `check --layout --shots`); it finds the engine in `$ACADEMY_ENGINE`, then the folder named in `.academy-engine`, then `../engine`. Or run `node <engine>/bin/academy.mjs <command> --root <this folder>`.

## What is left, and how long it takes

About **2 h 44 min** of a person's work before `academy check` passes, and about **3 h 16 min** more to clear its warnings, which the house standard also asks for. The estimate counts each task below and each finding of `academy check` as this migration found them; a coding agent does the same work faster, but a person still decides the outcomes of each session and reviews the checkpoints.

| Work | Minutes |
|---|---|
| The tasks under "Needs a person" (4) | 67 |
| 67 × `text/clock` (error) | 67 |
| 6 × `text/local-path` (error) | 30 |
| 24 × `quiz/why` (warning) | 120 |
| 13 × `slide/dense` (warning) | 65 |
| 1 × `notes/ratio` (warning) | 9 |
| 2 × `text/em-dash` (warning) | 2 |

Then `node academy.mjs check --layout --shots` opens every slide in Chrome (a few minutes for a course of five decks). It reports what the static check cannot see: a slide whose content is cut off or wider than the slide (`layout/overflow`, about 5 minutes each; long lines of code are the usual case, and the old system's own `?check` reported most of them too) and slides that do not reflow in the reading view on a phone (`layout/phone-wide`, `layout/phone-text`). Compare its contact sheets (`.shots/<lang>/<deck>/sheet-<n>.png`) with the old decks.

## Slides

Counted in the old deck and in the new source; "a → b" where they differ.

| Old deck | New deck | Slides | Speaker notes | Checkpoints | Lab slides | Pictures | Fragments | Break slides dropped |
|---|---|---|---|---|---|---|---|---|
| slides/day1.html | slides/day1.html | 55 | 51 | 4 | 4 | 18 | 53 | 0 |
| slides/day2.html | slides/day2.html | 56 | 56 | 7 | 4 | 19 | 119 | 0 |
| slides/day3.html | slides/day3.html | 55 | 55 | 6 | 4 | 24 | 27 | 0 |
| slides/day4.html | slides/day4.html | 56 | 56 | 7 | 4 | 17 | 73 | 0 |
| slides/day5.html | slides/day5.html | 21 | 4 | 0 | 0 | 0 | 0 | 0 |
| All | | 243 | 222 | 24 | 16 | 78 | 272 | 0 |

## Rebuilt from the old files

- "extensions" in course.json: assets/course.css, assets/migrated.css, assets/course.js, which the old decks loaded after the system's own files, so the course's own classes keep their look.
- slides/day1.html → slides/day1.html: "Store & Query", 4 sessions, 4 labs.
- slides/day1.html: 28 slides drawn with coordinates (elements placed by "left" and "top" in their style) got data-read="scaled": on a phone the reading view shows them as projected, zoomed to the column, since the layout is the content.
- slides/day2.html → slides/day2.html: "Ingest & Clean", 4 sessions, 4 labs.
- slides/day2.html: 29 slides drawn with coordinates (elements placed by "left" and "top" in their style) got data-read="scaled": on a phone the reading view shows them as projected, zoomed to the column, since the layout is the content.
- slides/day3.html → slides/day3.html: "Model & Test", 4 sessions, 4 labs.
- slides/day3.html: 27 slides drawn with coordinates (elements placed by "left" and "top" in their style) got data-read="scaled": on a phone the reading view shows them as projected, zoomed to the column, since the layout is the content.
- slides/day4.html → slides/day4.html: "Scale & Production", 4 sessions, 4 labs.
- slides/day4.html: 30 slides drawn with coordinates (elements placed by "left" and "top" in their style) got data-read="scaled": on a phone the reading view shows them as projected, zoomed to the column, since the layout is the content.
- slides/day5.html is the capstone day (no lab slides; presentation slides or a capstone title): its sessions are not sessions in the new engine, so data-session was removed from its section slides.
- 5 slides (slides/day1.html line 33, slides/day1.html line 156, slides/day2.html line 83, slides/day3.html line 58, slides/day5.html line 208) hold .pmap of assets/course.css, a grid of 6 fixed columns, which does not reflow in the reading view on a phone: they got data-read="scaled", so a phone shows them as projected, zoomed to the column.
- 1 slide (slides/day4.html line 484) holds .board of assets/course.css, a box 1440 px wide, which does not reflow in the reading view on a phone: it got data-read="scaled", so a phone shows it as projected, zoomed to the column.
- 6 course outcomes from the list of outcomes on index.html (LO1 to LO6).
- The audience, from the "Audience" paragraph of index.html.
- 1 prerequisite from the "Environment" paragraph of index.html.
- The capstone summary, from the "Capstone" section of index.html (its paragraphs and its list of options).
- The capstone submission, from the paragraph of the "Capstone" section that starts with "Submit".
- The capstone rubric: Functional end-to-end pipeline 30, Architecture & data modeling decisions 25, Data quality & testing 20, Orchestration & governance 15, Presentation & reproducibility 10.
- The capstone's talk_minutes (10) and qa_minutes (5), from the timers "Talk + demo" and "Q&A" of the old slides/day5.html line 157.
- Title "Modern Data Engineering", track ai-engineering, language en; the id "data-engineering" comes from the folder name.

## Needs a person

- assets/migrated.css holds the <style> rules of the old slides/day5.html line 10, which now apply to every deck. Look at those slides in the contact sheets of "academy check --shots"; move the rules into assets/course.css or delete the ones the engine's theme already gives. (about 10 min)
- 18 slides (slides/day1.html line 222, slides/day1.html line 257, slides/day1.html line 334, slides/day1.html line 367, slides/day1.html line 380, slides/day1.html line 537, slides/day2.html line 114, slides/day2.html line 175, slides/day2.html line 557, slides/day2.html line 633, slides/day3.html line 253, slides/day3.html line 269, slides/day3.html line 559, slides/day3.html line 653, slides/day4.html line 102, slides/day4.html line 580, slides/day4.html line 627, slides/day5.html line 256) hold .art-row of assets/course.css, a row that does not wrap, with a part of fixed width; the migration cannot tell whether it fits the column of a phone. Look at them with "academy check --layout" (layout/phone-wide names each slide that does not fit), then give .art-row a rule for narrow screens in assets/course.css (inside @media (max-width: 700px)), or mark the slide data-read="scaled". (about 5 min)
- Which outcomes each session serves: write "lo" for each of the 16 sessions in course.json (["LO1"], or more than one), from the session titles and the slides; the old decks do not say, so until then "academy check" reports every outcome as not covered (lo/uncovered). (about 32 min)
- 2 parts of index.html that the migration does not read (listed under "Left out of index.html"): keep or drop each. (about 20 min)

## What `academy check` reports

On the course as migrated, apart from the codes a task above clears (`lo/uncovered`). `node academy.mjs check` prints each place with what to do.

| Code | Level | Findings | Minutes | First places |
|---|---|---|---|---|
| `text/clock` | error | 67 | 67 | slides/day1.html:44, slides/day1.html:68, slides/day1.html:84 … |
| `text/local-path` | error | 6 | 30 | labs/solutions/tools/dagster.ipynb:779, labs/solutions/tools/spark.ipynb:85, labs/solutions/tools/spark.ipynb:883 … |
| `quiz/why` | warning | 24 | 120 | slides/day1.html:128, slides/day1.html:274, slides/day1.html:396 … |
| `slide/dense` | warning | 13 | 65 | slides/day1.html:65, slides/day1.html:113, slides/day1.html:180 … |
| `notes/ratio` | warning | 1 | 9 | slides/day5.html |
| `text/em-dash` | warning | 2 | 2 | slides/day1.html:167, slides/day1.html:175 |

## Left out of index.html

- index.html line 134: "Setup", the paragraph "Stack" (1 paragraph) is not on the new course page, which is generated from course.json. Move what is still true into course.json (a "sources" group for a list of links, "prerequisites" for what to prepare), README.md or a lab page, or drop it.
- index.html line 138: "Go deeper (optional)" (1 paragraph, a table of 12 rows, 20 links) is not on the new course page, which is generated from course.json. Move what is still true into course.json (a "sources" group for a list of links, "prerequisites" for what to prepare), README.md or a lab page, or drop it.

## Good to know

- Nothing.

## Break slides dropped

- None.

## Markup that does not parse strictly

The build parses slide sources strictly. Fix each place below in the slide source (close the element, quote the attribute, write `&lt;` for a "<" in text).

- None: every deck parses strictly.
