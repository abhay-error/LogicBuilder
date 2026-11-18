"""Parent-side wrapper: starts runner_child.py in a subprocess with a hard timeout."""
import json
import os
import subprocess
import sys
from pathlib import Path

CHILD = str(Path(__file__).with_name("runner_child.py"))
MAX_CODE = 64 * 1024


def execute(mode, code, timeout=6, **extra):
    if len(code) > MAX_CODE:
        return {"verdict": "CE", "error": {"type": "Error", "message": "Code too long", "line": None}}
    payload = json.dumps({"mode": mode, "code": code, **extra})
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        p = subprocess.run([sys.executable, "-I", CHILD], input=payload, capture_output=True,
                           text=True, encoding="utf-8", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"verdict": "TLE", "error": {"type": "TimeLimit",
                "message": f"Your code ran longer than {timeout}s (infinite loop?)", "line": None},
                "steps": [], "results": [], "stdout": ""}
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"verdict": "RE", "error": {"type": "InternalError",
                "message": (p.stderr or "no output")[-300:], "line": None},
                "steps": [], "results": [], "stdout": ""}
