#!/usr/bin/env bash
#
# Weekly cron entry point: fill in any missing publication-card summaries.
#
# The update-papers GitHub Action refreshes _data/papers.yml every Sunday and
# leaves `summary: ''` on papers it hasn't seen before. This script pulls that
# down and has Claude Code write the missing summaries — on the Claude
# subscription, so there is no API key and no per-call billing anywhere in the
# pipeline.
#
# Exits early (and quietly) when there is nothing to summarize, so the common
# case costs nothing.

set -euo pipefail

REPO="/home/abensonca/Work/Communication/Home Pages/abensonca.github.io"
CLAUDE="${CLAUDE:-/home/abensonca/.local/bin/claude}"

cd "$REPO"

echo "=== $(date -Is) refresh-summaries ==="

# Refuse to run on a dirty tree: this script commits and pushes, and we don't
# want it sweeping up unrelated work in progress.
if [ -n "$(git status --porcelain)" ]; then
    echo "Working tree is dirty; skipping. Run /refresh-summaries by hand when ready."
    git status --short
    exit 0
fi

git pull --ff-only

pending="$(python3 scripts/summaries.py pending --count)"
echo "Papers awaiting a summary: ${pending}"

if [ "$pending" -eq 0 ]; then
    echo "Nothing to do."
    exit 0
fi

# --permission-mode acceptEdits so the run doesn't stall on a prompt with
# nobody watching; the slash command's allowed-tools list bounds what it can do.
"$CLAUDE" --permission-mode acceptEdits -p "/refresh-summaries"

echo "=== $(date -Is) done ==="
