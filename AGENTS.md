# AGENTS.md — dcmQTreePy

A PySide6 + pydicom DICOM object editor, plus a Streamlit viewer at repo root
(`streamlit_dicom_viewer.py`). **Medical software**: it reads, edits, and
writes DICOM datasets. Changes to dataset handling are changes to clinical
data — one cause at a time, verified against real files.

## Skills to load

- **medical-software-standards** — always; this is a DICOM object editor.
- **python-development**, **test-writing-philosophy**,
  **systematic-test-design** — before writing or reviewing code/tests.
- **linting-efficiency**, **development-tooling-efficiency** — for the
  tooling loops (ruff, JSON tool output, token-cheap CI reads).
- **code-graph** — before exploring the codebase (cross-file questions).
- **gitea-base**, plus the seat you are actually in:
  **gitea-branch-work** / **gitea-prs-landing** when developing,
  **gitea-review** when reviewing.

## Commands

- `uv sync --dev` — install (after #1 lands; until then Poetry:
  `poetry install --with=dev`).
- `uv run pytest` — run tests. With no display:
  `QT_QPA_PLATFORM=offscreen uv run pytest`.
- `uv run ruff check` and `uv run ruff format` — lint and format.
- **Never `pip`.** The environment belongs to uv (formerly Poetry); direct pip
  desynchronises it from the lock.

## Where work happens

- **Gitea is the forge**: branches, PRs, **two reviewers** per PR.
- **GitHub is the public mirror.** Cyril pushes with mirror-tools
  (`push_up.sh`); **nobody pushes to GitHub directly.**
- **Issue numbers differ between Gitea and GitHub.** Never assume a number
  means the same thing on both. Commit messages say **"Refs #N"** — closing
  keywords (`Closes #N`) belong **only in a Gitea PR body**. (And the
  closing-keyword gate itself lives in mirror-tools' `push_up.sh`, not in a
  repo hook — absence of a local gate is not permission.)
- **CI split (the goal; not yet built):** macOS is intended to run on Gitea
  (`.gitea/workflows/`) and Linux on GitHub (`.github/workflows/`) — Stuart's
  split, recorded by Connor on #1. Gitea *has* macOS runners (other family
  repos run `runs-on: macos-latest` there). This repo has no
  `.gitea/workflows/` yet, so Gitea runs `.github/workflows/` and no macOS
  CI runs for it. The split is one workflow file away; whoever adds it picks
  the runner label — the file holds the rule, not a runner inventory. Incident reports and runner logs belong on
  the PR or the issue, not in this file.

## Stack and layout

- **PySide6 + pydicom** (plus pynetdicom, streamlit, dcm-mini-viewer).
- `dcmqtreepy/dcmQTree.py` — desktop entry point (`dcmQTreePy` script).
- `dcmqtreepy/mainwindow.py` and `dcmqtreepy/ui_*.py` — **generated** from
  `*.ui` (Qt Designer: `DICOMQTreeEditor.pyproject`). **Do not hand-edit**
  generated files; edit the `.ui` and regenerate.
- Private-tag dictionaries (`impac_privates.py`, `new_privates.py`) are
  **data consumed by pydicom**; `import_hex_legible_private_element_lists.py`
  is the generator that produces such dictionaries. Any change to the data
  files is a **data migration**: parity-check it, review it like a dictionary
  migration. (Connor, review of #7 — only the third file is a generator.)
- `help/` documentation; `sample_privates.json` is safe sample data,
  `local_privates.json` is user data — never commit edits to it.

## Versioning policy (medical)

Lockfile churn is behaviour churn. The uv migration (#1) is **tooling-only**:
pins resolve to the versions `poetry.lock` had (or the nearest that clears
critical alerts); major upgrades happen deliberately in **#4**. Any pin that
cannot match poetry.lock is noted **in the PR body, with why**.

## Testing rules

- Tests run inside the project env (`uv run pytest`, formerly `poetry run`)
  so pydicom/Qt resolve from the lock.
- **Real DICOM shapes**, not sanitized fixtures: odd VRs, private tags,
  unicode patient names, empty values, max-length strings. The question for
  every test: *would this catch a bug that only appears with real patient
  data?*
- **"Tests pass" is never a standalone report.** Say where it was run and
  what population it covers. GUI tests skipped via conftest/offscreen must be
  named as skips, never left to masquerade as passes.

## Branches, PRs, reviews

- `main` is protected on Gitea: PRs only; 1 approval required; a rejection
  blocks; approvals do not count once the PR's own files change; reviews are
  not auto-dismissed — re-approve deliberately at the new head.
- Branch names `<ai-name>/<issue-slug>`; two distinct reviewers on every PR
  (assign in the same request that creates the PR).

## The post-commit review hook

- Today: per-clone symlink `.git/hooks/post-commit` →
  `$HOME/ai/kindled_projects/kindled-code-review/hooks/post-commit`, installed
  by `install_kindled_postcommit.sh`; fresh clones do not get it automatically.
- **#6 (in flight)** bakes it into `.pre-commit-config.yaml`
  (`default_install_hook_types: [pre-commit, post-commit]` + local
  `kindled-review` hook) so `pre-commit install` wires review everywhere,
  **failing loudly and never silently** when the canonical hook is absent.
- Behaviour: exits early on `main`, never blocks a commit; on branches runs
  kindled-code-review (cross-file wall) then OpenCodeReview (local model).
- Review findings are **leads, not verdicts**: verify against the diff before
  changing or defending code. If the wall did not run, report UNVERIFIED.
