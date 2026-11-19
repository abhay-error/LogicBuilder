#!/usr/bin/env bash
# Installs Ollama and downloads local AI tutor models for LogicBuilder (macOS and Linux).
#
#   bash scripts/setup-ai.sh                  # auto profile, asks before installing
#   bash scripts/setup-ai.sh --profile standard --yes
#   bash scripts/setup-ai.sh --dry-run        # show what would happen, change nothing
#   bash scripts/setup-ai.sh --models qwen2.5-coder:3b,gemma3:4b
#
# Profiles (download sizes are approximate):
#   light     ~4 GB   for 8 GB RAM machines:   qwen2.5-coder:1.5b, gemma3:1b, deepseek-r1:1.5b
#   standard  ~13 GB  for 16 GB RAM machines:  qwen2.5-coder:7b,   gemma3:4b, deepseek-r1:8b
#   all       both sets      none   install Ollama only
# Kimi K2 is too large to run locally; use it through OpenRouter (see README).
set -u

PROFILE=""; MODELS=""; YES=0; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="${2:-}"; shift 2 ;;
    --models)  MODELS="${2:-}"; shift 2 ;;
    --yes|-y)  YES=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)"; exit 2 ;;
  esac
done
case "$PROFILE" in ""|light|standard|all|none) ;; *) echo "Profile must be light, standard, all or none."; exit 2 ;; esac

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
say()  { printf '  %s\n' "$*"; }
step() { printf '\n== %s\n' "$*"; }
run()  { # run "description" cmd...
  local what="$1"; shift
  if [ "$DRY" = 1 ]; then say "[dry run] would: $what"; else "$@"; fi
}
confirm() {
  [ "$YES" = 1 ] || [ "$DRY" = 1 ] && return 0
  printf '  %s [Y/n] ' "$1"; read -r a; [ -z "$a" ] || [[ "$a" =~ ^[Yy] ]]
}
api_up() { curl -fsS --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; }

# ---------------------------------------------------------------- choose models
ram_gb=0
if [ "$(uname)" = "Darwin" ]; then ram_gb=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 ))
elif command -v free >/dev/null 2>&1; then ram_gb=$(( $(free -m | awk '/^Mem:/{print $2}') / 1024 )); fi
if [ -z "$PROFILE" ] && [ -z "$MODELS" ]; then
  if [ "$ram_gb" -ge 14 ]; then PROFILE=standard; else PROFILE=light; fi
  say "Detected about ${ram_gb} GB RAM, using the '$PROFILE' profile (override with --profile)."
fi
LIGHT="qwen=qwen2.5-coder:1.5b gemma=gemma3:1b deepseek=deepseek-r1:1.5b"
STANDARD="qwen=qwen2.5-coder:7b gemma=gemma3:4b deepseek=deepseek-r1:8b"
WANT=""
if [ -n "$MODELS" ]; then for m in ${MODELS//,/ }; do WANT="$WANT x=$m"; done
else case "$PROFILE" in light) WANT="$LIGHT";; standard) WANT="$STANDARD";; all) WANT="$LIGHT $STANDARD";; esac; fi

echo "LogicBuilder AI setup"
say "Models to download: $(for p in $WANT; do printf '%s ' "${p#*=}"; done)"
[ "$DRY" = 1 ] && say "Dry run: nothing will be installed or changed."

# ---------------------------------------------------------------- 1. Ollama
step "1/4 Ollama"
if command -v ollama >/dev/null 2>&1; then
  say "Ollama is already installed: $(command -v ollama)"
else
  if [ "$(uname)" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then
      confirm "Install Ollama with Homebrew?" && run "brew install ollama" brew install ollama \
        || { say "Skipped."; exit 0; }
    else
      say "Homebrew not found. Download Ollama from https://ollama.com/download/mac, open it once, then re-run this script."
      [ "$DRY" = 1 ] || exit 1
    fi
  else
    say "This uses the official installer from ollama.com (it may ask for your sudo password)."
    confirm "Download and run https://ollama.com/install.sh ?" \
      && run "curl -fsSL https://ollama.com/install.sh | sh" sh -c 'curl -fsSL https://ollama.com/install.sh | sh' \
      || { say "Skipped. Install manually from https://ollama.com/download/linux"; exit 0; }
  fi
  if [ "$DRY" != 1 ] && ! command -v ollama >/dev/null 2>&1; then echo "Ollama was not found after install. Open a new terminal and re-run."; exit 1; fi
fi

# ---------------------------------------------------------------- 2. service
step "2/4 Ollama service"
if api_up; then say "Ollama is running."
else
  if [ "$DRY" = 1 ]; then say "[dry run] would: start 'ollama serve' in the background"
  else
    (nohup ollama serve >/dev/null 2>&1 &)
    ok=0; for _ in $(seq 1 30); do sleep 1; if api_up; then ok=1; break; fi; done
    [ "$ok" = 1 ] && say "Ollama started." || { echo "Ollama did not start within 30 seconds. Start it manually: ollama serve"; exit 1; }
  fi
fi

# ---------------------------------------------------------------- 3. models
step "3/4 Models"
HAVE=""; [ "$DRY" = 1 ] || HAVE="$(ollama list 2>/dev/null | awk 'NR>1{print $1}')"
PULLED=""
for p in $WANT; do
  fam="${p%%=*}"; m="${p#*=}"
  if printf '%s\n' "$HAVE" | grep -qx -e "$m" -e "$m:latest"; then say "$m is already downloaded."; PULLED="$PULLED $fam=$m"; continue; fi
  if [ "$DRY" = 1 ]; then say "[dry run] would: ollama pull $m"; continue; fi
  say "Downloading $m (this can take a while)..."
  if ollama pull "$m"; then PULLED="$PULLED $fam=$m"; else echo "  Could not download $m. Check the name at https://ollama.com/library and your connection."; fi
done

# ---------------------------------------------------------------- 4. tell LogicBuilder
step "4/4 LogicBuilder settings"
if [ -z "$MODELS" ] && [ "$PROFILE" != "all" ] && [ "$PROFILE" != "none" ] && [ -n "$PULLED" ]; then
  if [ "$DRY" = 1 ]; then say "[dry run] would: python3 scripts/set_models.py$PULLED"
  elif command -v python3 >/dev/null 2>&1; then python3 "$ROOT/scripts/set_models.py" $PULLED
  else say "python3 not found; set the model ids in the AI Tutor settings (gear icon) instead."; fi
else
  say "Nothing to update. In the AI Tutor panel (gear icon) enter the model ids you want to use."
fi

printf '\nDone.\n'
say "Start LogicBuilder, open the AI Tutor panel, pick 'Local (Ollama)'."
say "Models you have:  ollama list"
