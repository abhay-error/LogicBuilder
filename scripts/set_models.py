"""Point LogicBuilder's AI tutor at the local models you downloaded.

Usage:  python scripts/set_models.py qwen=qwen2.5-coder:1.5b gemma=gemma3:1b deepseek=deepseek-r1:1.5b
Writes the Ollama model ids into data/ai_config.json (keeps everything else, including any API key).
"""
import json
import os
import sys
from pathlib import Path

CFG = Path(os.environ.get("LB_DATA") or Path(__file__).resolve().parent.parent / "data") / "ai_config.json"
FAMILIES = {"qwen", "gemma", "deepseek", "kimi"}


def main(pairs):
    try:
        cfg = json.loads(CFG.read_text("utf-8"))
    except Exception:
        cfg = {}
    changed = []
    for p in pairs:
        fam, _, model = p.partition("=")
        if fam not in FAMILIES or not model:
            print(f"skipped '{p}' (expected family=model, family one of {sorted(FAMILIES)})")
            continue
        cfg.setdefault("families", {}).setdefault(fam, {})["ollama"] = model
        changed.append(f"{fam} -> {model}")
    if changed:
        CFG.parent.mkdir(exist_ok=True)
        CFG.write_text(json.dumps(cfg, indent=1), "utf-8")
        print("LogicBuilder AI settings updated: " + ", ".join(changed))


if __name__ == "__main__":
    main(sys.argv[1:])
