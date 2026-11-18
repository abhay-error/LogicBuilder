"""Content lint + engine self-test. Run:  python tests/selftest.py
Every problem's reference solution must pass all of its tests, and the tracer must work."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from app import sandbox  # noqa: E402
from content.lessons import LESSONS  # noqa: E402
from content.problems import PROBLEMS  # noqa: E402

fails = 0


def check(name, ok, info=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f"  {info}" if info and not ok else ""))
    fails += 0 if ok else 1


slugs = [p["slug"] for p in PROBLEMS]
check("problem slugs unique", len(slugs) == len(set(slugs)))
ids = [x["id"] for x in LESSONS]
check("lesson ids unique", len(ids) == len(set(ids)))

for p in PROBLEMS:
    r = sandbox.execute("test", p["reference"], entry=p["entry"], tests=p["tests"])
    check(f"reference solves {p['slug']}", r.get("verdict") == "AC", r)
    check(f"starter compiles {p['slug']}", sandbox.execute("run", p["starter"]).get("verdict") == "OK")
    check(f"{p['slug']} has 3 hints and a sample", len(p["hints"]) == 3 and any(t["sample"] for t in p["tests"]))
    wrong = sandbox.execute("test", p["starter"], entry=p["entry"], tests=p["tests"])
    check(f"empty starter fails {p['slug']}", wrong.get("verdict") != "AC")

for lsn in LESSONS:
    for b in lsn["blocks"]:
        if b["type"] == "code" and b.get("visualize"):
            t = sandbox.execute("trace", b["code"])
            check(f"lesson '{lsn['id']}' code traces", t.get("verdict") == "OK" and len(t["steps"]) > 0, t.get("error"))

from app import exercises  # noqa: E402

for ex_id, (lsn, b) in exercises.index(LESSONS).items():
    t = b["type"]
    pub = exercises.public(ex_id, lsn, b)
    check(f"{ex_id} ({t}): public payload hides answers", "answer" not in pub and "bug_line" not in pub and "explain" not in pub)
    if t == "quiz":
        check(f"{ex_id} quiz answer in range", 0 <= b["answer"] < len(b["options"]))
        check(f"{ex_id} grades", exercises.check(b, b["answer"])["correct"] and not exercises.check(b, (b["answer"] + 1) % len(b["options"]))["correct"])
    elif t == "predict":
        out = exercises._stdout(b["code"])
        check(f"{ex_id} predict code runs", out is not None and out.strip() != "", b["code"])
        check(f"{ex_id} predict grades", exercises.check(b, out)["correct"] and not exercises.check(b, "zzz")["correct"])
    elif t == "fill":
        filled = b["code"]
        for k, acc in b["blanks"].items():
            filled = filled.replace("{{" + k + "}}", acc[0])
        check(f"{ex_id} fill solution runs", sandbox.execute("run", filled).get("verdict") == "OK", filled)
        check(f"{ex_id} fill grades", exercises.check(b, {k: v[0] for k, v in b["blanks"].items()})["correct"]
              and not exercises.check(b, {k: "nope" for k in b["blanks"]})["correct"])
    elif t == "parsons":
        check(f"{ex_id} parsons solution runs", sandbox.execute("run", "\n".join(b["lines"]))["verdict"] == "OK")
        check(f"{ex_id} parsons shuffled differs", pub["lines"] != b["lines"] and sorted(pub["lines"]) == sorted(b["lines"]))
        check(f"{ex_id} parsons grades", exercises.check(b, b["lines"])["correct"] and not exercises.check(b, list(reversed(b["lines"])))["correct"])
    elif t == "trace_table":
        rows = exercises.trace_rows(b)
        check(f"{ex_id} trace table has rows", 1 <= len(rows) <= 10 and all("?" not in r for r in rows), rows)
        check(f"{ex_id} trace table grades", exercises.check(b, rows)["correct"] and not exercises.check(b, [["x"] * len(b["vars"])] * len(rows))["correct"])
    elif t == "bug":
        check(f"{ex_id} bug line in range", 1 <= b["bug_line"] <= len(b["code"].splitlines()))
        check(f"{ex_id} bug code runs", sandbox.execute("run", b["code"])["verdict"] == "OK")
        check(f"{ex_id} bug grades", exercises.check(b, b["bug_line"])["correct"] and not exercises.check(b, 99)["correct"])

t = sandbox.execute("trace", "def f(x):\n    return x*2\ny = f(2)\n")
check("trace records call/return", {"call", "return"} <= {s["event"] for s in t["steps"]})
check("infinite loop is capped", sandbox.execute("trace", "while True:\n    pass\n")["truncated"] is True)
check("run timeout works", sandbox.execute("run", "while True:\n    pass\n", timeout=2)["verdict"] == "TLE")
check("syntax error reported", sandbox.execute("run", "x = (")["verdict"] == "CE")

print("\nALL OK" if not fails else f"\n{fails} FAILED")
sys.exit(1 if fails else 0)
