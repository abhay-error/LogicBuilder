"""Per-learner JSON store + append-only event log.

Local MVP persistence behind a tiny interface (load/update/list/create). In production this
module is replaced by a PostgreSQL repository with the same functions (LLD §3, HLD §8).
"""
import json
import os
import re
import shutil
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
            "lessons": [], "problems": {}, "exercises": {}, "xp": 0, "days": {},
            "drafts": {},        # code drafts, written plans, playground code (key -> text)
            "lesson_state": {},  # lesson id -> {"step": blocks revealed so far}
            "prefs": {}}         # e.g. {"lang": "java"}


def _path(uid):
    return USERS / f"{uid}.json"


def _bak(uid):
    return USERS / f"{uid}.json.bak"


def load(uid):
    if not valid(uid):
        raise NotFound(uid)
    with _lock:
        p = _path(uid)
        try:
            d = json.loads(p.read_text("utf-8"))
        except FileNotFoundError:
            if uid != "default":
                raise NotFound(uid)
            d = _blank("default", "Me")
        except Exception:
            # The file is damaged. Never silently start from zero: recover the last good copy,
            # and keep the damaged file for inspection instead of overwriting it.
            d = None
            try:
                d = json.loads(_bak(uid).read_text("utf-8"))
            except Exception:
                pass
            try:
                p.replace(USERS / f"{uid}.corrupt-{int(time.time())}.json")
            except OSError:
                pass
            if d is None:
                d = _blank(uid, uid)
            else:
                _write(d, keep_backup=False)
        for k, v in _blank(uid, uid).items():  # forward-compatible defaults
            d.setdefault(k, v)
        return d


def _write(d, keep_backup=True):
    USERS.mkdir(parents=True, exist_ok=True)
    p = _path(d["id"])
    if keep_backup and p.exists():
        try:
            shutil.copyfile(p, _bak(d["id"]))  # last known-good copy, used if the main file ever gets damaged
        except OSError:
            pass
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1), "utf-8")
    tmp.replace(p)  # atomic on Windows, macOS and Linux


def get_last():
    """The learner who used the app last (so a cleared browser still opens on the right profile)."""
    try:
        uid = (DATA / "last_user.txt").read_text("utf-8").strip()
        if valid(uid) and (_path(uid).exists() or uid == "default"):
            return uid
    except OSError:
        pass
    return "default"


def set_last(uid):
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        (DATA / "last_user.txt").write_text(uid, "utf-8")
    except OSError:
        pass


DRAFT_KEY = re.compile(r"^[\w:.-]{1,80}$")
MAX_DRAFT = 60_000
MAX_DRAFTS = 400


def save_drafts(uid, items):
    """items: {key: text or None}. None deletes. Validated and size-capped."""
    def upd(d):
        for k, v in items.items():
            if not isinstance(k, str) or not DRAFT_KEY.match(k):
                continue
            if v is None:
                d["drafts"].pop(k, None)
            elif isinstance(v, str) and len(v) <= MAX_DRAFT and (k in d["drafts"] or len(d["drafts"]) < MAX_DRAFTS):
                d["drafts"][k] = v
    return update(uid, upd, touch=False)


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
