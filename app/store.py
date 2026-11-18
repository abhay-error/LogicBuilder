"""Per-learner JSON store + append-only event log.

Local MVP persistence behind a tiny interface (load/update/list/create). In production this
module is replaced by a PostgreSQL repository with the same functions (LLD §3, HLD §8).
"""
import json
import os
import re
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

DATA = Path(os.environ.get("LB_DATA") or Path(__file__).resolve().parent.parent / "data")
USERS = DATA / "users"
EVENTS = DATA / "events.jsonl"
_lock = threading.RLock()
UID = re.compile(r"^[a-z0-9_-]{1,32}$")


class NotFound(Exception):
    pass


def valid(uid):
    return isinstance(uid, str) and bool(UID.match(uid))


def _blank(uid, name, plan="free"):
    return {"id": uid, "name": name, "plan": plan, "created": datetime.now().isoformat(timespec="seconds"),
            "lessons": [], "problems": {}, "exercises": {}, "xp": 0, "days": {}}


def _path(uid):
    return USERS / f"{uid}.json"


def load(uid):
    if not valid(uid):
        raise NotFound(uid)
    with _lock:
        try:
            d = json.loads(_path(uid).read_text("utf-8"))
        except FileNotFoundError:
            if uid != "default":
                raise NotFound(uid)
            d = _blank("default", "Me")
        except Exception:
            d = _blank(uid, uid)
        for k, v in _blank(uid, uid).items():  # forward-compatible defaults
            d.setdefault(k, v)
        return d


def _write(d):
    USERS.mkdir(parents=True, exist_ok=True)
    p = _path(d["id"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1), "utf-8")
    tmp.replace(p)  # atomic on Windows, macOS and Linux


def update(uid, fn, touch=True):
    with _lock:
        d = load(uid)
        fn(d)
        if touch:
            today = date.today().isoformat()
            d["days"][today] = d["days"].get(today, 0) + 1
        _write(d)
        return d


def list_users():
    with _lock:
        out = []
        if USERS.exists():
            for f in sorted(USERS.glob("*.json")):
                try:
                    d = json.loads(f.read_text("utf-8"))
                    out.append({"id": d["id"], "name": d.get("name", d["id"]), "plan": d.get("plan", "free")})
                except Exception:
                    continue
        if not any(u["id"] == "default" for u in out):
            out.insert(0, {"id": "default", "name": "Me", "plan": "free"})
        return out


def create(name):
    name = (name or "").strip()[:40] or "Learner"
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "learner"
    with _lock:
        uid, n = base, 1
        while _path(uid).exists() or uid == "default":
            n += 1
            uid = f"{base}-{n}"
        _write(_blank(uid, name))
        return uid


def streak(d):
    n, day = 0, date.today()
    if day.isoformat() not in d["days"]:
        day -= timedelta(days=1)
    while day.isoformat() in d["days"]:
        n += 1
        day -= timedelta(days=1)
    return n


def log_event(uid, kind, **data):
    """Analytics-ready event stream (one JSON object per line)."""
    try:
        with _lock:
            DATA.mkdir(exist_ok=True)
            with EVENTS.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": int(time.time()), "user": uid, "type": kind, **data}) + "\n")
    except Exception:
        pass  # analytics must never break learning
