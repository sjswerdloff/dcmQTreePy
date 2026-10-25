#!/usr/bin/env bash
# kindled-review post-commit wrapper — runs the canonical kindled-code-review hook.
#
# Baked in via .pre-commit-config.yaml (kindled-review hook, stages: [post-commit]).
# Every clone that runs `pre-commit install` gets this.  The canonical hook lives
# OUTSIDE any clone, in shared infrastructure; this script finds it and execs it.
#
# The canonical hook exits early on main, never blocks a commit (post-commit
# exit code is ignored by git), and runs the cross-file wall + OCR on
# gemma-4-E4B-it-mlx-mxfp8.  OCR needs the local model endpoint — CI cannot
# run it.  This hook is for developers' commits only.
#
# INVARIANT: this script must never fail silently when the canonical hook is
# missing.  A new host without it must see a loud error on every commit.
set -euo pipefail

CANONICAL="${KINDLED_REVIEW_HOOK:-$HOME/ai/kindled_projects/kindled-code-review/hooks/post-commit}"

if [[ ! -f "$CANONICAL" ]]; then
    cat >&2 <<EOF
==========================================================================
kindled-review: CANONICAL HOOK NOT FOUND — review did NOT run.

  Expected: $CANONICAL
  Fix:      kindled-code-review is not deployed at ~/ai/kindled_projects
            on this host.  Ask Stuart to deploy it.

  This message prints on every commit until the hook is installed.
==========================================================================
EOF
    exit 0
fi

exec "$CANONICAL"
