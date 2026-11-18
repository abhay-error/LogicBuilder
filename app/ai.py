"""AI tutor: one OpenAI-compatible client that talks to open models through
Ollama (local) or OpenRouter (cloud). Families: Qwen, Gemma, DeepSeek, Kimi.

Model ids change often — edit them in the UI (gear icon) or data/ai_config.json.
"""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

CFG_PATH = Path(__file__).resolve().parent.parent / "data" / "ai_config.json"

DEFAULTS = {
    "provider": "ollama",
    "family": "qwen",
    "providers": {
        # 127.0.0.1, not "localhost": on Linux/macOS localhost may resolve to ::1 first
        "ollama": {"base_url": "http://127.0.0.1:11434/v1", "api_key": ""},
        "openrouter": {"base_url": "https://openrouter.ai/api/v1", "api_key": ""},
    },
    "families": {
        "qwen": {"label": "Qwen (coder)", "ollama": "qwen2.5-coder:7b", "openrouter": "qwen/qwen-2.5-coder-32b-instruct"},
        "gemma": {"label": "Gemma", "ollama": "gemma3:4b", "openrouter": "google/gemma-3-27b-it"},
        "deepseek": {"label": "DeepSeek", "ollama": "deepseek-r1:8b", "openrouter": "deepseek/deepseek-chat"},
        "kimi": {"label": "Kimi K2", "ollama": "", "openrouter": "moonshotai/kimi-k2"},
    },
}

SYSTEM = """You are the AI tutor inside LogicBuilder, a learning app that takes people from zero to confident in coding logic and DSA.
Rules:
- Teach logic and thinking first, syntax second. Use short everyday analogies, then a tiny code example.
- Be concise (under ~200 words unless asked for more). Lessons use Python; for practice and the playground use the
  language the learner chose (Python, JavaScript, TypeScript, Java, C++, Go or C#). When useful, mention language-specific
  interview gotchas (integer overflow, integer division, string comparison, sort defaults).
- Refer to the learner's own code and the current line when you have it. Walk through values step by step.
- For practice problems: do NOT hand over the full solution. Guide with questions and progressively stronger hints
  (idea -> approach -> pseudocode). Only show full code if the learner explicitly asks after trying.
- When it matters, mention time/space complexity in plain words (e.g. "doubles with every item" for O(n^2)-style growth).
- Teach the method: Understand -> Examples (by hand) -> Plan (plain words) -> Code -> Test -> Improve. Ask the learner
  to try a tiny example by hand before you explain. Prefer one guiding question over a long explanation.
- If the learner is stuck or discouraged, be encouraging and make the next step very small.
"""


def _deep_merge(base, over):
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config():
    try:
        saved = json.loads(CFG_PATH.read_text("utf-8"))
    except Exception:
        saved = {}
    cfg = _deep_merge(DEFAULTS, saved)
    if not cfg["providers"]["openrouter"]["api_key"]:
        cfg["providers"]["openrouter"]["api_key"] = os.environ.get("OPENROUTER_API_KEY", "")
    return cfg


def save_config(patch):
    cfg = load_config()
    if patch.get("provider") in cfg["providers"]:
        cfg["provider"] = patch["provider"]
    if patch.get("family") in cfg["families"]:
        cfg["family"] = patch["family"]
    for fam, models in (patch.get("models") or {}).items():
        if fam in cfg["families"] and isinstance(models, dict):
            for prov in ("ollama", "openrouter"):
                if isinstance(models.get(prov), str):
                    cfg["families"][fam][prov] = models[prov].strip()
    for prov, p in (patch.get("providers") or {}).items():
        if prov in cfg["providers"] and isinstance(p, dict):
            if isinstance(p.get("base_url"), str) and p["base_url"].strip():
                cfg["providers"][prov]["base_url"] = p["base_url"].strip().rstrip("/")
            if isinstance(p.get("api_key"), str) and p["api_key"].strip():
                cfg["providers"][prov]["api_key"] = p["api_key"].strip()
    CFG_PATH.parent.mkdir(exist_ok=True)
    CFG_PATH.write_text(json.dumps(cfg, indent=1), "utf-8")
    return cfg


def public_config():
    """Config safe to send to the browser (never includes API keys)."""
    cfg = load_config()
    return {
        "provider": cfg["provider"],
        "family": cfg["family"],
        "families": cfg["families"],
        "providers": {k: {"base_url": v["base_url"], "has_key": bool(v["api_key"])}
                      for k, v in cfg["providers"].items()},
        "ollama_installed": ollama_models(cfg),
    }


def ollama_models(cfg):
    base = cfg["providers"]["ollama"]["base_url"].replace("/v1", "")
    try:
        with urllib.request.urlopen(base + "/api/tags", timeout=1.5) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return None  # Ollama not running


def build_messages(history, ctx):
    sys_prompt = SYSTEM
    parts = []
    if ctx.get("lesson"):
        parts.append(f"Current lesson: {ctx['lesson']}")
    if ctx.get("problem"):
        parts.append(f"Current practice problem:\n{ctx['problem']}")
    if ctx.get("exercise"):
        parts.append(f"The learner is on this exercise (do NOT reveal the answer, guide them):\n{ctx['exercise'][:1500]}")
    if ctx.get("plan"):
        parts.append(f"Learner's written plan for the problem (review it kindly, point out gaps):\n{ctx['plan'][:1500]}")
    if ctx.get("code"):
        lang = re.sub(r"[^a-z+#]", "", str(ctx.get("lang") or "python").lower()) or "python"
        parts.append(f"The learner is coding in {lang}. Answer in {lang} unless they ask otherwise.\nLearner's current code:\n```{lang}\n{ctx['code'][:4000]}\n```")
    if ctx.get("result"):
        parts.append(f"Latest run result: {ctx['result'][:1200]}")
    if ctx.get("step"):
        parts.append(f"Visualizer is paused at: {ctx['step'][:600]}")
    if parts:
        sys_prompt += "\n\nContext:\n" + "\n\n".join(parts)
    msgs = [{"role": "system", "content": sys_prompt}]
    for m in history[-12:]:
        if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
            msgs.append({"role": m["role"], "content": m["content"][:6000]})
    return msgs


def stream_chat(history, ctx, provider, family, emit):
    """Calls emit(text) for each streamed token."""
    cfg = load_config()
    prov = cfg["providers"].get(provider)
    fam = cfg["families"].get(family)
    if not prov or not fam:
        return emit("[AI error: unknown provider or model family]")
    model = fam.get(provider, "")
    if not model:
        return emit(f"[{fam['label']} has no model configured for {provider}. "
                    f"Pick another provider (e.g. OpenRouter) or set a model id in the settings.]")
    headers = {"Content-Type": "application/json"}
    if provider == "openrouter":
        if not prov["api_key"]:
            return emit("[OpenRouter needs an API key. Open settings (gear) and paste it, "
                        "or set the OPENROUTER_API_KEY environment variable.]")
        headers["Authorization"] = "Bearer " + prov["api_key"]
        headers["X-Title"] = "LogicBuilder"
    body = json.dumps({"model": model, "stream": True, "temperature": 0.4,
                       "messages": build_messages(history, ctx)}).encode()
    req = urllib.request.Request(prov["base_url"] + "/chat/completions", data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            for raw in r:
                line = raw.decode("utf-8", "ignore").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content")
                except Exception:
                    continue
                if delta:
                    emit(delta)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        if e.code == 404 and provider == "ollama":
            emit(f"[Model '{model}' is not installed. Run:  ollama pull {model}]")
        else:
            emit(f"[AI error {e.code}: {detail}]")
    except urllib.error.URLError as e:
        if provider == "ollama":
            emit("[Can't reach Ollama. Install it from https://ollama.com, start it, then run:  "
                 f"ollama pull {model}]")
        elif "CERTIFICATE_VERIFY_FAILED" in str(e.reason):
            emit("[SSL certificates missing. On macOS run 'Install Certificates.command' in your Python "
                 "folder (Applications/Python 3.x), or: pip install certifi]")
        else:
            emit(f"[Network error: {e.reason}]")
    except Exception as e:  # noqa
        emit(f"[AI error: {e}]")
