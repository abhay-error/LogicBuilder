#!/usr/bin/env bash
# macOS: double-click in Finder (first time: chmod +x start.command start.sh)
exec bash "$(dirname "$0")/start.sh" "$@"
