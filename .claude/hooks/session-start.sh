#!/usr/bin/env bash
# SessionStart hook: ensure dependencies are installed and API keys visible.
# Runs on every Claude Code session start (local and web).
set -euo pipefail

cd "$(dirname "$0")/../.."

# Install uv if not present (web sandbox may not have it).
if ! command -v uv >/dev/null 2>&1; then
  echo "[session-start] installing uv..." >&2
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || true
  export PATH="$HOME/.local/bin:$PATH"
fi

# Sync dependencies if pyproject.toml exists.
if [ -f pyproject.toml ]; then
  uv sync --quiet 2>/dev/null || echo "[session-start] uv sync skipped (offline or first-run)" >&2
fi

# Surface API key status without leaking the value.
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "[session-start] ANTHROPIC_API_KEY: set"
elif [ -f .env ] && grep -q '^ANTHROPIC_API_KEY=..*$' .env 2>/dev/null; then
  echo "[session-start] ANTHROPIC_API_KEY: set (.env)"
else
  echo "[session-start] ANTHROPIC_API_KEY: MISSING — Phase 1 evolve will not run"
fi
