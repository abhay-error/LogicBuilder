"""Vercel entry point: serves the whole app (static files + REST API) from one Python function.

Vercel only allows writes under /tmp, so progress on the hosted demo is temporary.
For real, persistent progress run LogicBuilder locally (see README).
"""
import os
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LB_HOSTED", "1")
os.environ.setdefault("LB_DATA", "/tmp/logicbuilder-data")

from server import Handler as _Handler  # noqa: E402


class handler(_Handler):  # Vercel looks for a class named `handler`
    def _restore_path(self):
        """vercel.json rewrites every URL to this function as /api/index?__p=<original path>; put the original back."""
        u = urlsplit(self.path)
        q = parse_qsl(u.query, keep_blank_values=True)
        orig = next((v for k, v in q if k == "__p"), None)
        if orig is None:
            if u.path in ("/api/index", "/api/index.py"):
                orig = "/"
            else:
                return
        rest = [(k, v) for k, v in q if k != "__p"]
        self.path = "/" + orig.lstrip("/") + ("?" + urlencode(rest) if rest else "")

    def do_GET(self):
        self._restore_path()
        super().do_GET()

    def do_POST(self):
        self._restore_path()
        super().do_POST()
