"""Runs learner code in an isolated child process.

Reads one JSON payload from stdin, writes one JSON result to the real stdout.
modes: "run"   -> execute, capture output
       "trace" -> execute with sys.settrace, record execution steps (LLD §5)
       "test"  -> define function, run it against test cases
"""
import copy
import io
import json
import math
import sys
import types

try:  # extra safety on Linux/macOS (no `resource` module on Windows; wall-clock timeout still applies)
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    if sys.platform.startswith("linux"):  # RLIMIT_AS is unreliable on macOS
        resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
except Exception:
    pass

sys.stdin.reconfigure(encoding="utf-8")
payload = json.loads(sys.stdin.read())
mode = payload["mode"]
code = payload["code"]
REAL_OUT = sys.stdout
OUT_CAP = 4000
MAX_STEPS = 1000
MAX_ITEMS = 30
MAX_FRAMES = 30


class Cap(io.StringIO):
    def write(self, s):
        if self.tell() < OUT_CAP:
            super().write(s)
        return len(s)


class StopTrace(BaseException):
    pass


def ser(v, d=0):
    """Safe, bounded serializer for values shown in the visualizer."""
    if v is None:
        return {"t": "NoneType", "v": None}
    if isinstance(v, bool):
        return {"t": "bool", "v": v}
    if isinstance(v, int):
        return {"t": "int", "v": v if abs(v) < 10**15 else str(v)}
    if isinstance(v, float):
        return {"t": "float", "v": v if math.isfinite(v) else repr(v)}
    if isinstance(v, str):
        return {"t": "str", "v": v if len(v) <= 80 else v[:80] + "…"}
    if isinstance(v, (list, tuple, set, frozenset)) and d < 3:
        items = list(v)
        return {"t": "list" if isinstance(v, list) else type(v).__name__,
                "items": [ser(x, d + 1) for x in items[:MAX_ITEMS]],
                "more": max(0, len(items) - MAX_ITEMS)}
    if isinstance(v, dict) and d < 3:
        items = list(v.items())
        return {"t": "dict",
                "entries": [[ser(k, d + 1), ser(x, d + 1)] for k, x in items[:MAX_ITEMS]],
                "more": max(0, len(items) - MAX_ITEMS)}
    try:
        r = repr(v)
    except Exception:
        r = "<object>"
    return {"t": "obj", "v": r[:60]}


def snap(frame):
    out = {}
    for k, v in list(frame.f_locals.items()):
        if k.startswith("__") or isinstance(v, (types.FunctionType, types.ModuleType, type)):
            continue
        out[k] = ser(v)
    return out


def user_error(e, tb):
    line = None
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == "<user>":
            line = tb.tb_lineno
        tb = tb.tb_next
    return {"type": type(e).__name__, "message": str(e)[:300], "line": line}


def compile_user():
    try:
        return compile(code, "<user>", "exec"), None
    except SyntaxError as e:
        return None, {"type": "SyntaxError", "message": str(e.msg), "line": e.lineno}


def finish(obj):
    REAL_OUT.write(json.dumps(obj))
    REAL_OUT.flush()


cap = Cap()
compiled, cerr = compile_user()
if cerr:
    finish({"verdict": "CE", "error": cerr, "steps": [], "stdout": ""})
    sys.exit(0)

if mode == "run":
    sys.stdout = cap
    err = None
    try:
        exec(compiled, {"__name__": "__main__"})
    except BaseException as e:  # noqa
        err = user_error(e, e.__traceback__)
    sys.stdout = REAL_OUT
    finish({"verdict": "RE" if err else "OK", "error": err, "stdout": cap.getvalue()})

elif mode == "trace":
    steps = []

    def stack_of(frame):
        fr, f = [], frame
        while f is not None and len(fr) < MAX_FRAMES:
            if f.f_code.co_filename == "<user>":
                name = f.f_code.co_name
                fr.append({"fn": "main" if name == "<module>" else name,
                           "line": f.f_lineno, "locals": snap(f)})
            f = f.f_back
        fr.reverse()
        return fr

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != "<user>":
            return None
        if event == "call" and frame.f_code.co_name == "<module>":
            return tracer
        if event in ("line", "call", "return", "exception"):
            if len(steps) >= MAX_STEPS:
                raise StopTrace()
            s = {"i": len(steps), "line": frame.f_lineno, "event": event,
                 "stack": stack_of(frame), "stdout": cap.getvalue()}
            if event == "return":
                s["ret"] = ser(arg)
            if event == "exception":
                s["exc"] = f"{arg[0].__name__}: {arg[1]}"[:200]
            steps.append(s)
        return tracer

    sys.stdout = cap
    err, truncated = None, False
    sys.settrace(tracer)
    try:
        exec(compiled, {"__name__": "__main__"})
    except StopTrace:
        truncated = True
    except BaseException as e:  # noqa
        err = user_error(e, e.__traceback__)
    finally:
        sys.settrace(None)
        sys.stdout = REAL_OUT
    finish({"verdict": "RE" if err else "OK", "error": err, "steps": steps,
            "truncated": truncated, "stdout": cap.getvalue()})

elif mode == "test":
    entry, tests = payload["entry"], payload["tests"]
    g = {"__name__": "__main__"}
    sys.stdout = cap
    try:
        exec(compiled, g)
    except BaseException as e:  # noqa
        sys.stdout = REAL_OUT
        finish({"verdict": "RE", "error": user_error(e, e.__traceback__), "results": [], "stdout": cap.getvalue()})
        sys.exit(0)
    fn = g.get(entry)
    if not callable(fn):
        sys.stdout = REAL_OUT
        finish({"verdict": "CE", "error": {"type": "NameError",
                "message": f"Define a function named {entry}", "line": None}, "results": [], "stdout": ""})
        sys.exit(0)

    def norm(x):
        return json.loads(json.dumps(x, default=list))

    results = []
    for t in tests:
        try:
            actual = norm(fn(*copy.deepcopy(t["input"])))
            exp = t["expected"]
            if t.get("cmp") == "unordered":
                ok = sorted(actual, key=repr) == sorted(exp, key=repr)
            else:
                ok = actual == exp
            results.append({"pass": ok, "actual": actual})
        except BaseException as e:  # noqa
            er = user_error(e, e.__traceback__)
            results.append({"pass": False, "error": f"{er['type']}: {er['message']}"})
    sys.stdout = REAL_OUT
    allpass = all(r["pass"] for r in results)
    any_err = any("error" in r for r in results)
    finish({"verdict": "AC" if allpass else ("RE" if any_err else "WA"),
            "results": results, "stdout": cap.getvalue()})
