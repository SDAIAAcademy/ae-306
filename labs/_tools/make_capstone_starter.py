"""Write the participants' capstone starter from the trainer's reference solution.

    cd labs
    uv run python _tools/make_capstone_starter.py

Reads solutions/capstone_pipeline.py and writes capstone/pipeline.py: every body between
"# BEGIN SOLUTION" and "# END SOLUTION" becomes a NotImplementedError naming the lab to reuse.
"""
from __future__ import annotations

import re
from pathlib import Path

LABS = Path(__file__).resolve().parents[1]
SRC = LABS / "solutions" / "capstone_pipeline.py"
DST = LABS / "capstone" / "pipeline.py"

HEADER = '''"""Qafila margin mart, end to end: your capstone pipeline.

    cd labs
    uv run python capstone/pipeline.py                  # the whole pipeline, November batch fixed
    uv run python capstone/pipeline.py --batch broken   # the contract must block: the mart is not refreshed

Each step below names the lab whose code it reuses. Replace each NotImplementedError with your own code; the
steps you have not built yet are reported, not fatal, so you can run the file at any point. The run writes
labs/artifacts/capstone/run_report.json (row counts, test results and run time per step): commit a copy of it as
evidence. The brief and the rubric are in capstone/README.md.
"""'''


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    text = re.sub(r'\A""".*?"""', lambda _: HEADER, text, count=1, flags=re.S)

    def stub(m: re.Match) -> str:
        indent = m.group(1)
        return f'{indent}raise NotImplementedError("your code here")\n'

    text, n = re.subn(r"^([ \t]*)# BEGIN SOLUTION\n.*?^[ \t]*# END SOLUTION\n", stub, text, flags=re.S | re.M)
    DST.write_text(text, encoding="utf-8", newline="\n")
    print(f"{DST.relative_to(LABS).as_posix()}: {n} steps left to the participant")


if __name__ == "__main__":
    main()
