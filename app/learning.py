"""Learning engine: spaced repetition, concept mastery, badges (LLD §7, simplified for the MVP)."""
from datetime import date, timedelta

from . import store

INTERVALS = [1, 3, 7, 14, 30, 60]  # days between successful reviews


def record_exercise(user, ex_id, correct):
    e = user["exercises"].setdefault(ex_id, {"ok": 0, "bad": 0, "n": 0, "due": date.today().isoformat()})
    today = date.today()
    first_ok = correct and e["ok"] == 0
    if correct:
        e["ok"] += 1
        e["n"] += 1
        e["due"] = (today + timedelta(days=INTERVALS[min(e["n"] - 1, len(INTERVALS) - 1)])).isoformat()
    else:
        e["bad"] += 1
        e["n"] = 0
        e["due"] = today.isoformat()
    if first_ok:
        user["xp"] += 2
    return first_ok


def due_ids(user, limit=10):
    today = date.today().isoformat()
    due = [(e["due"], k) for k, e in user["exercises"].items() if e["due"] <= today and (e["ok"] or e["bad"])]
    return [k for _, k in sorted(due)][:limit]


def mastery(user, lessons, problems, ex_index):
    """concept -> {mastery 0..1, items, level}. Mastery = mean of item scores (explainable on purpose)."""
    per = {}

    def add(concept, score, level):
        c = per.setdefault(concept, {"scores": [], "level": level})
        c["scores"].append(score)
        c["level"] = min(c["level"], level)

    for lsn in lessons:
        ids = [k for k, (l, _) in ex_index.items() if l["id"] == lsn["id"]]
        if ids:
            score = sum(1 for k in ids if user["exercises"].get(k, {}).get("ok", 0) > 0) / len(ids)
        else:
            score = 1.0 if lsn["id"] in user["lessons"] else 0.0
        for c in lsn.get("concepts", []):
            add(c, score, lsn["level"])
    for p in problems:
        st = user["problems"].get(p["slug"], {}).get("status", "unseen")
        score = {"solved": 1.0, "attempted": 0.3}.get(st, 0.0)
        for c in p["concepts"]:
            add(c, score, p["level"])
    return sorted(({"concept": c, "mastery": round(sum(v["scores"]) / len(v["scores"]), 2), "items": len(v["scores"]), "level": v["level"]}
                   for c, v in per.items()), key=lambda x: (x["level"], x["concept"]))


def badges(user):
    solved = [v for v in user["problems"].values() if v["status"] == "solved"]
    ok_ex = sum(1 for e in user["exercises"].values() if e["ok"] > 0)
    st = store.streak(user)
    spec = [
        ("first-lesson", "First steps", "Finish your first lesson", len(user["lessons"]) >= 1),
        ("ten-exercises", "Warm-up", "Answer 10 exercises correctly", ok_ex >= 10),
        ("first-solve", "Problem solver", "Solve your first practice problem", len(solved) >= 1),
        ("no-hints", "On your own", "Solve a problem without any hints", any(v.get("hints", 0) == 0 for v in solved)),
        ("five-solves", "On a roll", "Solve 5 problems", len(solved) >= 5),
        ("streak-3", "3-day streak", "Practice 3 days in a row", st >= 3),
        ("streak-7", "Week warrior", "Practice 7 days in a row", st >= 7),
    ]
    return [{"id": i, "title": t, "desc": d, "earned": bool(e)} for i, t, d, e in spec]
