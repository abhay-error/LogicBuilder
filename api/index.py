"""Vercel entry point: serves the whole app (static files + REST API) from one Python function.

Vercel only allows writes under /tmp, so progress on the hosted demo is temporary.
For real, persistent progress run LogicBuilder locally (see README).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LB_HOSTED", "1")
os.environ.setdefault("LB_DATA", "/tmp/logicbuilder-data")

from server import Handler as _Handler  # noqa: E402


class handler(_Handler):  # Vercel looks for a class named `handler`
    pass
