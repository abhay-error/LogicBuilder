#!/usr/bin/env bash
# Linux / macOS launcher. Run:  bash start.sh   (or chmod +x start.sh && ./start.sh)
cd "$(dirname "$0")" || exit 1
for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1; then exec "$py" server.py "$@"; fi
done
echo "Python 3.9+ not found. Install it from https://www.python.org/downloads/ (or your package manager)."
exit 1
