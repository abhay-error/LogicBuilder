"""LogicBuilder local server. Zero dependencies: `python server.py` then open http://127.0.0.1:8000

Layers (LLD §2): routes (this file) -> services (app/*) -> store. Binds to localhost only.
Env: PORT, LB_PAYWALL=1 (enforce premium lessons for plan != pro), LB_ADMIN=0 (disable /api/admin).
"""
import json
import mimetypes
import os
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from app import ai, exercises, langs, learning, sandbox, store  # noqa: E402
from content import rosetta  # noqa: E402
from content.lessons import LESSONS  # noqa: E402
from content.problems import PROBLEMS  # noqa: E402
from content.signatures import SIGS  # noqa: E402

WEB = ROOT / "web"
HOST, PORT = "127.0.0.1", 8000
PAYWALL = os.environ.get("LB_PAYWALL") == "1"
ADMIN = os.environ.get("LB_ADMIN", "1") != "0"
LESSON = {x["id"]: x for x in LESSONS}
PROBLEM = {p["slug"]: p for p in PROBLEMS}
EX = exercises.index(LESSONS)


class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def locked(lesson, user):
    return PAYWALL and lesson.get("premium") and user.get("plan") != "pro"


def public_problem(p, user):
    return {"slug": p["slug"], "title": p["title"], "difficulty": p["difficulty"], "level": p["level"],
            "concepts": p["concepts"], "status": user["problems"].get(p["slug"], {}).get("status", "unseen")}


def public_lesson(lsn):
    blocks = []
    for i, b in enumerate(lsn["blocks"]):
        if b["type"] in exercises.INTERACTIVE:
            blocks.append(exercises.public(exercises.exercise_id(lsn["id"], i), lsn, b))
        else:
            blocks.append(b)
    return {"id": lsn["id"], "title": lsn["title"], "level": lsn["level"], "minutes": lsn["minutes"], "blocks": blocks}


def get_lang(b):
    lang = b.get("lang") or "python"
    if lang not in langs.LANGS:
        raise ApiError(400, "VALIDATION_ERROR", "Unknown language")
    return lang


def run_problem(uid, slug, code, submit, lang="python"):
    p = PROBLEM[slug]
    tests = p["tests"] if submit else [t for t in p["tests"] if t["sample"]]
    r = langs.judge(lang, code, SIGS[slug], p["entry"], tests)
    out = []
    for t, res in zip(tests, r.get("results", [])):
        row = {"pass": res["pass"], "sample": t["sample"]}
        if t["sample"]:  # hidden tests never reveal inputs/expected values
            row.update(input=t["input"], expected=t["expected"], actual=res.get("actual"))
        if "error" in res:
            row["error"] = res["error"]
        out.append(row)
    resp = {"verdict": r["verdict"], "error": r.get("error"), "results": out, "stdout": r.get("stdout", ""),
            "passed": sum(x["pass"] for x in out), "total": len(out) if r.get("results") else len(tests)}
    if submit and r["verdict"] != "NOLANG":
        def upd(d):
            e = d["problems"].setdefault(slug, {"status": "attempted", "attempts": 0, "hints": 0})
            e["attempts"] += 1
            if r["verdict"] == "AC":
                solved_in = e.setdefault("langs", [])
                if lang not in solved_in:
                    solved_in.append(lang)
                if e["status"] != "solved":
                    e["status"] = "solved"
                    gain = int(10 * p["difficulty"] * (1.5 if e["hints"] == 0 else 1))
                    d["xp"] += gain
                    resp["xp_gained"] = gain
                elif len(solved_in) > 1 and solved_in[-1] == lang:  # small bonus for solving in a new language
                    d["xp"] += 5
                    resp["xp_gained"] = 5
        store.update(uid, upd)
        store.log_event(uid, "submit", problem=slug, lang=lang, verdict=r["verdict"], passed=resp["passed"], total=resp["total"])
        if r["verdict"] == "AC":
            resp["complexity"] = p["complexity"]
    return resp


def admin_stats():
    users = [store.load(u["id"]) for u in store.list_users()]
    lessons = [{"id": l["id"], "title": l["title"], "completed": sum(1 for u in users if l["id"] in u["lessons"])} for l in LESSONS]
    probs = []
    for p in PROBLEMS:
        rec = [u["problems"][p["slug"]] for u in users if p["slug"] in u["problems"]]
        solved = [r for r in rec if r["status"] == "solved"]
        probs.append({"slug": p["slug"], "title": p["title"], "learners": len(rec), "solved": len(solved),
                      "avg_attempts": round(sum(r["attempts"] for r in rec) / len(rec), 1) if rec else 0,
                      "avg_hints": round(sum(r["hints"] for r in rec) / len(rec), 1) if rec else 0})
    ex = []
    for k, (lsn, b) in EX.items():
        tot_ok = sum(u["exercises"].get(k, {}).get("ok", 0) for u in users)
        tot_bad = sum(u["exercises"].get(k, {}).get("bad", 0) for u in users)
        if tot_ok + tot_bad:
            ex.append({"id": k, "lesson": lsn["title"], "type": b["type"], "attempts": tot_ok + tot_bad,
                       "accuracy": round(tot_ok / (tot_ok + tot_bad), 2)})
    ex.sort(key=lambda x: x["accuracy"])
    return {"users": [{"id": u["id"], "name": u["name"], "plan": u["plan"], "xp": u["xp"], "lessons": len(u["lessons"]),
                       "solved": sum(1 for v in u["problems"].values() if v["status"] == "solved"),
                       "streak": store.streak(u)} for u in users],
            "lessons": lessons, "problems": probs, "hardest_exercises": ex[:8], "paywall": PAYWALL}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    # ---- helpers
    def send_json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 256 * 1024:
            return {}
        try:
            v = json.loads(self.rfile.read(n) or b"{}")
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}

    def uid(self):
        u = self.headers.get("X-User", "default")
        if not store.valid(u):
            raise ApiError(400, "BAD_USER", "Invalid user id")
        return u

    # ---- dispatch with one error envelope (LLD §8)
    def _dispatch(self, fn):
        try:
            fn(urlparse(self.path).path)
        except ApiError as e:
            self.send_json({"error": {"code": e.code, "message": e.message}}, e.status)
        except store.NotFound:
            self.send_json({"error": {"code": "USER_NOT_FOUND", "message": "Unknown learner profile"}}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa
            self.send_json({"error": {"code": "INTERNAL", "message": f"{type(e).__name__}: {e}"}}, 500)

    def do_GET(self):
        self._dispatch(self.get)

    def do_POST(self):
        self._dispatch(self.post)

    # ---- GET
    def get(self, path):
        if not path.startswith("/api/"):
            return self.static(path)
        if path == "/api/users":
            return self.send_json(store.list_users())
        if path == "/api/ai/config":
            return self.send_json(ai.public_config())
        if path == "/api/languages":
            return self.send_json(langs.catalog(refresh="refresh=1" in (urlparse(self.path).query or "")))
        if path == "/api/rosetta":
            return self.send_json({"order": rosetta.LANG_ORDER, "concepts": rosetta.CONCEPTS, "advice": rosetta.ADVICE})
        if path == "/api/admin/stats":
            if not ADMIN:
                raise ApiError(403, "FORBIDDEN", "Admin disabled")
            return self.send_json(admin_stats())
        uid = self.uid()
        user = store.load(uid)
        if path == "/api/lessons":
            return self.send_json([{"id": x["id"], "title": x["title"], "level": x["level"], "minutes": x["minutes"],
                                    "done": x["id"] in user["lessons"], "premium": bool(x.get("premium")),
                                    "locked": bool(locked(x, user))} for x in LESSONS])
        m = re.fullmatch(r"/api/lessons/([\w-]+)", path)
        if m:
            lsn = LESSON.get(m[1])
            if not lsn:
                raise ApiError(404, "LESSON_NOT_FOUND", "Lesson not found")
            if locked(lsn, user):
                raise ApiError(402, "PAYWALL", "This lesson is part of the Pro plan")
            return self.send_json(public_lesson(lsn))
        if path == "/api/problems":
            return self.send_json([public_problem(p, user) for p in PROBLEMS])
        m = re.fullmatch(r"/api/problems/([\w-]+)", path)
        if m:
            p = PROBLEM.get(m[1])
            if not p:
                raise ApiError(404, "PROBLEM_NOT_FOUND", "Problem not found")
            d = public_problem(p, user)
            d.update(statement=p["statement"], starter=p["starter"], starters=langs.starters(SIGS[p["slug"]], p["entry"], p["starter"]),
                     entry=p["entry"], hint_count=len(p["hints"]),
                     hints_used=user["problems"].get(p["slug"], {}).get("hints", 0),
                     samples=[{"input": t["input"], "expected": t["expected"]} for t in p["tests"] if t["sample"]])
            return self.send_json(d)
        if path == "/api/progress":
            due = len(learning.due_ids(user, 999))
            return self.send_json({"xp": user["xp"], "streak": store.streak(user), "plan": user["plan"], "name": user["name"],
                                   "lessons_done": len(user["lessons"]), "lessons_total": len(LESSONS),
                                   "solved": sum(1 for v in user["problems"].values() if v["status"] == "solved"),
                                   "problems_total": len(PROBLEMS), "review_due": due,
                                   "badges": learning.badges(user)})
        if path == "/api/skills":
            return self.send_json(learning.mastery(user, LESSONS, PROBLEMS, EX))
        if path == "/api/review/due":
            out = []
            for k in learning.due_ids(user, 10):
                if k in EX:
                    lsn, b = EX[k]
                    out.append(exercises.public(k, lsn, b))
            return self.send_json(out)
        if path == "/api/export":
            return self.send_json(user)
        raise ApiError(404, "NOT_FOUND", "Not found")

    # ---- POST
    def post(self, path):
        b = self.body()
        if path == "/api/ai/config":
            ai.save_config(b)
            return self.send_json(ai.public_config())
        if path == "/api/ai/chat":
            return self.chat(b)
        if path == "/api/users":
            return self.send_json({"id": store.create(b.get("name"))})
        uid = self.uid()
        code = b.get("code", "") if isinstance(b.get("code", ""), str) else ""
        if path == "/api/trace":
            if get_lang(b) != "python":
                raise ApiError(400, "UNSUPPORTED", "The step-by-step visualizer supports Python only")
            return self.send_json(sandbox.execute("trace", code))
        if path == "/api/run":
            lang = get_lang(b)
            store.log_event(uid, "run", lang=lang)
            return self.send_json(langs.run_program(lang, code))
        if path == "/api/me":
            def upd(d):
                if isinstance(b.get("name"), str) and b["name"].strip():
                    d["name"] = b["name"].strip()[:40]
                if b.get("plan") in ("free", "pro"):  # local demo: no billing. Production: set by the payment webhook.
                    d["plan"] = b["plan"]
            store.update(uid, upd, touch=False)
            store.log_event(uid, "profile_update", plan=b.get("plan"))
            return self.send_json({"ok": True})
        if path == "/api/exercises/check":
            ex = EX.get(b.get("id"))
            if not ex:
                raise ApiError(404, "EXERCISE_NOT_FOUND", "Exercise not found")
            lsn, blk = ex
            if locked(lsn, store.load(uid)):
                raise ApiError(402, "PAYWALL", "Pro plan required")
            reveal = bool(b.get("reveal"))
            res = exercises.check(blk, b.get("answer"), reveal)
            if not reveal:
                store.update(uid, lambda d: learning.record_exercise(d, b["id"], res["correct"]))
                store.log_event(uid, "exercise", id=b["id"], correct=res["correct"])
            return self.send_json(res)
        m = re.fullmatch(r"/api/problems/([\w-]+)/(run|submit|trace|hint)", path)
        if m:
            slug, action = m.groups()
            p = PROBLEM.get(slug)
            if not p:
                raise ApiError(404, "PROBLEM_NOT_FOUND", "Problem not found")
            if action in ("run", "submit"):
                return self.send_json(run_problem(uid, slug, code, action == "submit", get_lang(b)))
            if action == "trace":  # trace the learner's function on the first sample input (Python only)
                if get_lang(b) != "python":
                    raise ApiError(400, "UNSUPPORTED", "The step-by-step visualizer supports Python only")
                s = next(t for t in p["tests"] if t["sample"])
                call = f"\n__result = {p['entry']}(*{s['input']!r})\nprint(__result)\n"
                return self.send_json(sandbox.execute("trace", code + call))
            level = b.get("level")
            if not isinstance(level, int) or not 1 <= level <= len(p["hints"]):
                raise ApiError(400, "VALIDATION_ERROR", "Bad hint level")

            def upd(d):
                e = d["problems"].setdefault(slug, {"status": "attempted", "attempts": 0, "hints": 0})
                e["hints"] = max(e["hints"], level)
            store.update(uid, upd)
            store.log_event(uid, "hint", problem=slug, level=level)
            return self.send_json({"level": level, "text": p["hints"][level - 1]})
        m = re.fullmatch(r"/api/lessons/([\w-]+)/complete", path)
        if m:
            lsn = LESSON.get(m[1])
            if not lsn:
                raise ApiError(404, "LESSON_NOT_FOUND", "Lesson not found")
            if locked(lsn, store.load(uid)):
                raise ApiError(402, "PAYWALL", "Pro plan required")

            def upd(d):
                if m[1] not in d["lessons"]:
                    d["lessons"].append(m[1])
                    d["xp"] += 10
            d = store.update(uid, upd)
            store.log_event(uid, "lesson_complete", lesson=m[1])
            nxt = next((x["id"] for x in LESSONS if x["id"] not in d["lessons"] and not locked(x, d)), None)
            return self.send_json({"ok": True, "xp": d["xp"], "next": nxt})
        raise ApiError(404, "NOT_FOUND", "Not found")

    def chat(self, b):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        cfg = ai.load_config()

        def emit(s):
            self.wfile.write(s.encode("utf-8"))
            self.wfile.flush()
        try:
            ai.stream_chat(b.get("messages", []), b.get("context", {}) or {},
                           b.get("provider") or cfg["provider"], b.get("family") or cfg["family"], emit)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        f = (WEB / rel).resolve()
        if WEB.resolve() not in f.parents or not f.is_file():
            raise ApiError(404, "NOT_FOUND", "Not found")
        data = f.read_bytes()
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        if f.suffix in (".html", ".js", ".css"):
            ctype += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets two servers share a port; keep it only on POSIX.
    allow_reuse_address = os.name != "nt"


def bind():
    """Use $PORT / --port if given, else 8000; fall back to the next free ports."""
    start = PORT
    if "--port" in sys.argv:
        start = int(sys.argv[sys.argv.index("--port") + 1])
    elif os.environ.get("PORT", "").isdigit():
        start = int(os.environ["PORT"])
    for port in range(start, start + 20):
        try:
            return Server((HOST, port), Handler), port
        except OSError:
            continue
    sys.exit(f"No free port found in {start}-{start + 19}. Use --port N.")


if __name__ == "__main__":
    if sys.version_info < (3, 9):
        sys.exit("LogicBuilder needs Python 3.9 or newer (you have %d.%d)." % sys.version_info[:2])
    srv, port = bind()
    url = f"http://{HOST}:{port}"
    print(f"LogicBuilder running at {url}  (Ctrl+C to stop)")
    if PAYWALL:
        print("Paywall ON: premium lessons need the Pro plan.")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
