"""Tests for the AI setup helpers. Run: python tests/setup_test.py
Uses a temporary data folder (LB_DATA); it never touches your real settings."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fails = 0


def check(name, ok, info=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {info}"))
    fails += 0 if ok else 1


tmp = tempfile.mkdtemp()
env = {**os.environ, "LB_DATA": tmp}
cfg = Path(tmp) / "ai_config.json"
cfg.write_text(json.dumps({"provider": "openrouter", "providers": {"openrouter": {"api_key": "KEEP-ME"}}}), "utf-8")


def run(*args):
    return subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "set_models.py"), *args], env=env, capture_output=True, text=True)


r = run("qwen=qwen2.5-coder:3b", "gemma=gemma3:1b", "bogus=x", "nocolon")
d = json.loads(cfg.read_text("utf-8"))
check("model ids written", d["families"]["qwen"]["ollama"] == "qwen2.5-coder:3b" and d["families"]["gemma"]["ollama"] == "gemma3:1b", r.stdout + r.stderr)
check("unknown families and malformed pairs skipped", "bogus" not in d["families"] and "skipped" in r.stdout)
check("existing settings and API key preserved", d["provider"] == "openrouter" and d["providers"]["openrouter"]["api_key"] == "KEEP-ME")

# the app reads the same file
sys.path.insert(0, str(ROOT))
os.environ["LB_DATA"] = tmp
from app import ai  # noqa: E402

check("app picks up the written model", ai.load_config()["families"]["qwen"]["ollama"] == "qwen2.5-coder:3b")
check("model name validator accepts real names", all(ai.MODEL_RE.match(m) for m in ["qwen2.5-coder:7b", "gemma3:4b", "deepseek-r1:8b", "library/llama3.2:3b"]))
check("model name validator rejects junk", not any(ai.MODEL_RE.match(m) for m in ["", "a b", "x;y", "-bad", "a:" + "z" * 60]))

# the shell script must parse, and --dry-run must change nothing
bash = shutil.which("bash")
if bash:
    sh = "scripts/setup-ai.sh"  # relative: some Windows bash builds mangle absolute Windows paths
    r = subprocess.run([bash, "-n", sh], capture_output=True, text=True, cwd=ROOT)
    check("setup-ai.sh has valid syntax", r.returncode == 0, r.stderr)
    r = subprocess.run([bash, sh, "--dry-run", "--profile", "standard"], capture_output=True, text=True, env=env, cwd=ROOT)
    check("setup-ai.sh --dry-run lists the standard models and exits cleanly",
          r.returncode == 0 and "qwen2.5-coder:7b" in r.stdout and "Dry run" in r.stdout, r.stdout[-300:] + r.stderr[-300:])
    check("--dry-run left settings untouched", json.loads(cfg.read_text("utf-8"))["families"]["qwen"]["ollama"] == "qwen2.5-coder:3b")
    bad = subprocess.run([bash, sh, "--profile", "huge"], capture_output=True, text=True, cwd=ROOT)
    check("setup-ai.sh rejects an unknown profile", bad.returncode == 2)
else:
    print("SKIP setup-ai.sh tests: bash not available")

print("\nALL OK" if not fails else f"\n{fails} FAILED")
sys.exit(1 if fails else 0)
