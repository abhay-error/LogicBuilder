"""Exercise service: builds browser-safe exercise payloads and grades answers server-side.

Answers never leave the server (protects content in a business setting, HLD §11).
Wherever possible the truth is *computed* by really running the code, not hand-typed:
  predict      -> expected output = stdout of the code
  trace_table  -> rows = what the tracer records
  parsons      -> any order that runs and prints the same output is accepted
"""
import random
import re

from . import sandbox

INTERACTIVE = {"quiz", "predict", "fill", "parsons", "trace_table", "bug"}
_cache = {}


def exercise_id(lesson_id, idx):
    return f"{lesson_id}#{idx}"


def index(lessons):
    """id -> (lesson, block) for every interactive block."""
    out = {}
    for lsn in lessons:
        for i, b in enumerate(lsn["blocks"]):
            if b["type"] in INTERACTIVE:
                out[exercise_id(lsn["id"], i)] = (lsn, b)
    return out


# ---------------------------------------------------------------- truth computation
def _stdout(code):
    key = ("out", code)
    if key not in _cache:
        r = sandbox.execute("run", code)
        _cache[key] = r.get("stdout", "") if r.get("verdict") == "OK" else None
    return _cache[key]


def _fmt(v):
    if v is None:
        return "?"
    t = v["t"]
    if t == "NoneType":
        return "None"
    if t == "bool":
        return "True" if v["v"] else "False"
    if t in ("int", "float", "str"):
        return str(v["v"])
    if t == "list":
        return "[" + ", ".join(_fmt(x) for x in v["items"]) + "]"
    return str(v.get("v", t))


def trace_rows(b):
    key = ("rows", b["code"], b["line"], tuple(b["vars"]))
    if key not in _cache:
        r = sandbox.execute("trace", b["code"])
        rows = []
        for s in r.get("steps", []):
            if s["event"] == "line" and s["line"] == b["line"] and s["stack"] and s["stack"][-1]["fn"] == "main":
                loc = s["stack"][-1]["locals"]
                rows.append([_fmt(loc.get(v)) for v in b["vars"]])
        _cache[key] = rows[:10]
    return _cache[key]


# ---------------------------------------------------------------- normalisation
def _n_out(s):
    lines = [re.sub(r"\s+", " ", ln.strip()) for ln in str(s).strip().splitlines()]
    return "\n".join(lines).replace('"', "'")


def _n_tok(s):
    return re.sub(r"\s+", "", str(s)).replace('"', "'")


def _n_cell(s):
    return str(s).strip().strip("'\"")


# ---------------------------------------------------------------- public payload
def public(ex_id, lesson, b):
    p = {"id": ex_id, "type": b["type"], "prompt": b.get("prompt", ""), "lesson": lesson["title"]}
    t = b["type"]
    if t == "quiz":
        p["options"] = b["options"]
    elif t == "predict":
        p["code"] = b["code"]
        p["lines"] = max(1, (_stdout(b["code"]) or "").strip().count("\n") + 1)
    elif t == "fill":
        p["code"] = b["code"]
        p["blanks"] = list(b["blanks"].keys())
    elif t == "parsons":
        lines = list(b["lines"])
        rnd = random.Random(ex_id)
        shuffled = lines[:]
        for _ in range(10):
            rnd.shuffle(shuffled)
            if shuffled != lines:
                break
        p["lines"] = shuffled
    elif t == "trace_table":
        p.update(code=b["code"], line=b["line"], vars=b["vars"], rows=len(trace_rows(b)))
    elif t == "bug":
        p["code"] = b["code"]
    return p


# ---------------------------------------------------------------- grading
def check(b, answer, reveal=False):
    """Returns {correct, explain?, detail?, solution?}."""
    t = b["type"]
    res = {"correct": False, "detail": {}}
    if t == "quiz":
        res["correct"] = answer == b["answer"]
        sol = b["answer"]
    elif t == "predict":
        exp = b.get("answer") or _stdout(b["code"]) or ""
        res["correct"] = isinstance(answer, str) and _n_out(answer) == _n_out(exp)
        sol = exp.strip()
    elif t == "fill":
        ans = answer if isinstance(answer, dict) else {}
        per = {k: _n_tok(ans.get(k, "")) in {_n_tok(x) for x in accepted} for k, accepted in b["blanks"].items()}
        res["correct"], res["detail"] = all(per.values()), {"blanks": per}
        sol = {k: v[0] for k, v in b["blanks"].items()}
    elif t == "parsons":
        want = b["lines"]
        got = answer if isinstance(answer, list) else []
        exact = got == want
        ok = exact
        if not exact and sorted(got) == sorted(want):
            ref = _stdout("\n".join(want) + "\n")
            mine = _stdout("\n".join(got) + "\n")
            ok = mine is not None and ref is not None and mine == ref
        res["correct"] = ok
        res["detail"] = {"positions": [i < len(got) and got[i] == w for i, w in enumerate(want)]}
        sol = want
    elif t == "trace_table":
        rows = trace_rows(b)
        got = answer if isinstance(answer, list) else []
        cells = [[(r < len(got) and c < len(got[r]) and _n_cell(got[r][c]) == _n_cell(v)) for c, v in enumerate(row)]
                 for r, row in enumerate(rows)]
        res["correct"], res["detail"] = bool(rows) and all(all(r) for r in cells), {"cells": cells}
        sol = rows
    elif t == "bug":
        res["correct"] = answer == b["bug_line"]
        sol = b["bug_line"]
    else:
        raise ValueError("not an exercise")
    if res["correct"] or reveal:
        res["explain"] = b.get("explain", "")
        res["solution"] = sol
    return res
