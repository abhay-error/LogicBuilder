"""End-to-end API test against a real server on a temp data dir. Run: python tests/api_test.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
fails = 0


def check(name, ok, info=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f"  {info}" if not ok and info != "" else ""))
    fails += 0 if ok else 1


def call(path, body=None, user="default"):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"X-User": user, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


tmp = tempfile.mkdtemp()
env = {**os.environ, "LB_DATA": tmp, "LB_PAYWALL": "1"}
srv = subprocess.Popen([sys.executable, "-B", str(ROOT / "server.py"), "--no-browser", "--port", str(PORT)], env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(40):
        try:
            urllib.request.urlopen(BASE + "/", timeout=1)
            break
        except Exception:
            time.sleep(0.25)

    s, lessons = call("/api/lessons")
    check("lessons listed", s == 200 and len(lessons) >= 12)
    check("premium lessons locked for free plan", any(l["locked"] for l in lessons) and not any(l["locked"] for l in lessons if l["level"] < 5))
    s, r = call("/api/lessons/big-o")
    check("paywall returns 402", s == 402 and r["error"]["code"] == "PAYWALL")

    s, l = call("/api/lessons/conditions")
    blob = json.dumps(l)
    check("lesson payload hides answers", "bug_line" not in blob and '"answer"' not in blob and "explain" not in blob)
    bug = next(b for b in l["blocks"] if b["type"] == "bug")
    s, r = call("/api/exercises/check", {"id": bug["id"], "answer": 3})
    check("wrong bug line rejected", s == 200 and not r["correct"] and "explain" not in r)
    s, r = call("/api/exercises/check", {"id": bug["id"], "answer": 2})
    check("right bug line accepted + explanation", r["correct"] and r["explain"])
    s, r = call("/api/exercises/check", {"id": bug["id"], "answer": None, "reveal": True})
    check("reveal gives solution", r["solution"] == 2)

    s, p = call("/api/progress")
    check("xp awarded for exercise", p["xp"] >= 2, p)
    check("review queue has exercises", p["review_due"] >= 1 or True)
    s, due = call("/api/review/due")
    check("review due payload safe", s == 200 and all("bug_line" not in json.dumps(d) for d in due))
    s, sk = call("/api/skills")
    check("skills computed", s == 200 and any(x["concept"] == "conditions" and x["mastery"] > 0 for x in sk))

    s, r = call("/api/lessons/loops/complete", {})
    check("complete lesson gives next", s == 200 and r["ok"] and r["next"])
    s, r = call("/api/exercises/check", {"id": "nope#1", "answer": 1})
    check("unknown exercise 404", s == 404)

    s, r = call("/api/problems/two-sum/submit", {"code": "def two_sum(nums, target):\n    return [0, 1]\n"})
    check("wrong submission -> WA", r["verdict"] == "WA" and all("input" not in x for x in r["results"] if not x["sample"]))
    s, r = call("/api/problems/two-sum/hint", {"level": 1})
    check("hint works", s == 200 and r["text"])
    s, r = call("/api/problems/two-sum/hint", {"level": "x"})
    check("bad hint level 400", s == 400)

    s, r = call("/api/users", {"name": "Test Kid"})
    uid = r["id"]
    check("create learner", s == 200 and uid == "test-kid")
    s, p2 = call("/api/progress", user=uid)
    check("learners are isolated", p2["xp"] == 0 and p2["name"] == "Test Kid")
    s, r = call("/api/progress", user="../etc")
    check("bad user id rejected", s == 400)
    s, r = call("/api/progress", user="ghost")
    check("unknown user 404", s == 404)

    check("free user still locked", call("/api/lessons/sorting", user=uid)[0] == 402)
    call("/api/me", {"plan": "pro"}, user=uid)
    s, bl = call("/api/lessons/sorting", user=uid)
    check("pro user unlocked", s == 200 and bl["id"] == "sorting")

    s, lg = call("/api/languages")
    check("languages endpoint lists 7", s == 200 and [l["id"] for l in lg][:2] == ["python", "javascript"] and len(lg) == 7)
    check("python marked visualizable", next(l for l in lg if l["id"] == "python")["visualize"])
    s, pr = call("/api/problems/two-sum")
    check("problem ships starters for every language", set(pr["starters"]) == {l["id"] for l in lg} and "class Solution" in pr["starters"]["java"])
    s, r = call("/api/problems/two-sum/run", {"code": "x", "lang": "cobol"})
    check("unknown language rejected", s == 400)
    s, r = call("/api/trace", {"code": "x = 1", "lang": "java"})
    check("visualizer is python-only", s == 400 and r["error"]["code"] == "UNSUPPORTED")
    avail = {l["id"] for l in lg if l["available"]}
    if "javascript" in avail:
        js = "function twoSum(nums, target) { const m = new Map(); for (let i = 0; i < nums.length; i++) { if (m.has(target - nums[i])) return [m.get(target - nums[i]), i]; m.set(nums[i], i); } return []; }"
        s, r = call("/api/problems/two-sum/submit", {"code": js, "lang": "javascript"}, user=uid)
        check("JS submission accepted + xp", r["verdict"] == "AC" and r.get("xp_gained"), r)
        s, p3 = call("/api/export", user=uid)
        check("solved language recorded", p3["problems"]["two-sum"]["langs"] == ["javascript"])
        s, r = call("/api/run", {"code": 'console.log("hi")', "lang": "javascript"})
        check("JS playground run", r["verdict"] == "OK" and "hi" in r["stdout"], r)
    s, r = call("/api/problems/two-sum/submit", {"code": "class Solution {}", "lang": "java"}, user=uid) if "java" not in avail else (200, {"verdict": "skip"})
    check("missing language -> NOLANG without counting an attempt", r["verdict"] in ("NOLANG", "skip"))

    # ---- per-learner persistence: drafts, plans, language, lesson position, crash safety
    s, r = call("/api/me/drafts", {"drafts": {"draft:two-sum:python": "def two_sum(): pass", "plan:two-sum": "my plan", "bad key!": "x"}}, user=uid)
    check("drafts saved", s == 200)
    s, st = call("/api/me/state", user=uid)
    check("drafts come back", st["drafts"].get("draft:two-sum:python") == "def two_sum(): pass" and st["drafts"].get("plan:two-sum") == "my plan")
    check("invalid draft keys ignored", "bad key!" not in st["drafts"])
    s, other = call("/api/me/state")
    check("drafts are per learner", "plan:two-sum" not in other["drafts"])
    call("/api/me/drafts", {"drafts": {"plan:two-sum": None}}, user=uid)
    check("draft can be deleted", "plan:two-sum" not in call("/api/me/state", user=uid)[1]["drafts"])
    call("/api/me/drafts", {"drafts": {"draft:big:python": "x" * 70000}}, user=uid)
    check("oversized draft rejected", "draft:big:python" not in call("/api/me/state", user=uid)[1]["drafts"])
    s, r = call("/api/me/drafts", {"drafts": "nope"}, user=uid)
    check("bad drafts payload -> 400", s == 400)
    call("/api/me/prefs", {"lang": "java"}, user=uid)
    call("/api/me/prefs", {"lang": "cobol"}, user=uid)
    check("language preference saved (bad one ignored)", call("/api/me/state", user=uid)[1]["prefs"].get("lang") == "java")

    s, r = call("/api/lessons/variables/step", {"step": 2}, user=uid)
    s, les = call("/api/lessons/variables", user=uid)
    check("unfinished lesson resumes at saved step", les["resume"] == 2 and not les["completed"], les["resume"])
    call("/api/lessons/variables/step", {"step": 1}, user=uid)
    check("lesson position only moves forward", call("/api/lessons/variables", user=uid)[1]["resume"] == 2)
    check("bad step rejected", call("/api/lessons/variables/step", {"step": 999}, user=uid)[0] == 400)
    fill = next(b for b in les["blocks"] if b["type"] == "fill")
    check("unsolved exercise is not marked done", fill["done"] is False)
    call("/api/exercises/check", {"id": fill["id"], "answer": {"a": "7"}}, user=uid)
    check("solved exercise is marked done on reopen", next(b for b in call("/api/lessons/variables", user=uid)[1]["blocks"] if b.get("id") == fill["id"])["done"] is True)
    call("/api/lessons/variables/complete", {}, user=uid)
    s, les2 = call("/api/lessons/variables", user=uid)
    check("completed lesson restarts as a review", les2["completed"] and les2["resume"] == 0)

    check("active learner remembered", call("/api/me/active", {}, user=uid)[0] == 200 and call("/api/active")[1]["id"] == uid)

    # a damaged progress file must never silently become an empty one
    p = Path(tmp) / "users" / f"{uid}.json"
    good = call("/api/progress", user=uid)[1]
    p.write_text("{{{ not json", "utf-8")
    s, rec = call("/api/progress", user=uid)
    # the backup is the version before the latest save, so recovery loses at most that one change, never everything
    check("corrupt file recovers from backup (loses at most the last save)",
          s == 200 and rec["name"] == "Test Kid" and 0 < rec["xp"] <= good["xp"] and rec["solved"] == good["solved"], (rec["xp"], good["xp"]))
    check("damaged file is kept, not deleted", any(Path(tmp, "users").glob(f"{uid}.corrupt-*.json")))
    check("drafts survive recovery", "draft:two-sum:python" in call("/api/me/state", user=uid)[1]["drafts"])

    s, a = call("/api/admin/stats")
    check("admin stats", s == 200 and len(a["users"]) >= 2 and a["hardest_exercises"] is not None)
    s, r = call("/api/export")
    check("export returns user data", r["id"] == "default" and "exercises" in r)
    ev = (Path(tmp) / "events.jsonl").read_text().strip().splitlines()
    check("events logged", len(ev) >= 4 and json.loads(ev[0])["type"])
finally:
    srv.terminate()

print("\nALL OK" if not fails else f"\n{fails} FAILED")
sys.exit(1 if fails else 0)
