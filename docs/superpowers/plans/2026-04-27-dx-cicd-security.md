# DX + CI/CD + Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Python tooling (ruff, pre-commit, pyproject.toml), GitHub Actions CI for both Python and React, gitleaks secret scanning, and clean up stale debug files.

**Architecture:** Non-breaking infrastructure layer — no production code changes. Each task is independently committable and does not affect runtime behavior.

**Tech Stack:** ruff 0.9.x, pre-commit, gitleaks, GitHub Actions (ubuntu-latest), pytest (already installed)

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `pyproject.toml` | Python project metadata + ruff + pytest config |
| Create | `.pre-commit-config.yaml` | ruff, gitleaks, whitespace hooks |
| Create | `.gitleaks.toml` | Allowlist for known non-secrets |
| Modify | `.gitignore` | Add `config.backup-*`, `*.bak` patterns |
| Delete | `config.backup-*.json` (×8) | Stale debug snapshots, untracked |
| Create | `.github/workflows/python-ci.yml` | Lint + test on push/PR |
| Create | `.github/workflows/react-ci.yml` | ESLint + Vite build on push/PR |

---

## Task 1: Create pyproject.toml

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Create the file**

```toml
[project]
name = "moca"
version = "0.1.0"
requires-python = ">=3.11"

[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP"]
ignore = [
    "E501",   # line length handled by formatter
    "E711",   # comparison to None — SQLite rows use this idiom
    "E712",   # comparison to True/False — common throughout
    "UP007",  # X | Y union syntax requires Python 3.10+
    "UP035",  # deprecated import paths — audit separately
    "F841",   # local variable assigned but never used — scraper locals
]
per-file-ignores = { "tests/*" = ["F811"] }

[tool.ruff.format]
quote-style = "double"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v"
```

- [ ] **Step 2: Install ruff and verify it runs**

```bash
pip install ruff
ruff check . --statistics
```

Expected: a list of violation counts per rule. There will be violations — that's fine, we fix them in Task 2.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pyproject.toml with ruff + pytest config"
```

---

## Task 2: Auto-fix ruff violations

**Files:**
- Modify: `*.py` (root-level) — ruff auto-fixes

- [ ] **Step 1: Run auto-fix (safe rules only)**

```bash
ruff check . --fix --unsafe-fixes=false
```

This auto-fixes: unused imports (F401), unsorted imports (I001), redundant escape chars, etc. It will NOT touch logic.

- [ ] **Step 2: Run formatter**

```bash
ruff format .
```

- [ ] **Step 3: Review the diff**

```bash
git diff --stat
```

Scan the output. If any file shows hundreds of changed lines, open it and confirm the changes are cosmetic (import reordering, quote normalization). Do NOT commit if logic changed.

- [ ] **Step 4: Run tests to confirm nothing broke**

```bash
pytest tests/ -v --ignore=tests/test_scraper.py
```

Expected: same pass/fail results as before the ruff run. The scraper tests are excluded because they require live Playwright.

- [ ] **Step 5: Run ruff check to confirm clean**

```bash
ruff check .
```

Expected: exit 0. If there are remaining violations (ruff can't auto-fix everything), either:
- Suppress with `# noqa: EXXX` on that line if it's a legitimate false positive
- Fix manually (e.g. bare `except:` → `except Exception:`)

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -m "chore: apply ruff auto-fix and format"
```

---

## Task 3: Add pre-commit hooks

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Install pre-commit**

```bash
pip install pre-commit
```

- [ ] **Step 2: Create .pre-commit-config.yaml**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.1
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.2
    hooks:
      - id: gitleaks

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
        exclude: "mass-market-app/dist/"
      - id: check-yaml
      - id: check-json
        exclude: "tsconfig.*|package-lock\\.json"
      - id: check-merge-conflict
```

- [ ] **Step 3: Install the git hook**

```bash
pre-commit install
```

Expected: `pre-commit installed at .git/hooks/pre-commit`

- [ ] **Step 4: Run against all files once to confirm clean state**

```bash
pre-commit run --all-files
```

Expected: all hooks pass (since we just ran ruff in Task 2). If gitleaks reports false positives, handle them in Task 4 before this completes.

- [ ] **Step 5: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: add pre-commit hooks (ruff, gitleaks, whitespace)"
```

---

## Task 4: Add gitleaks allowlist + update .gitignore

**Files:**
- Create: `.gitleaks.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Create .gitleaks.toml**

```toml
title = "MOCA gitleaks config"

[allowlist]
description = "Files that are already gitignored or contain only test/example values"
paths = [
    '''\.env.*''',
    '''config\.json''',
    '''tests/''',
    '''mass-market-app/dist/''',
    '''data/''',
]

# Suppress known false positives from example/documentation code
[[rules]]
id = "vapid-example"
description = "VAPID key example in comments"
regex = '''BNLRx.*=='''
tags = ["false-positive"]
```

- [ ] **Step 2: Update .gitignore — add backup patterns**

Open `.gitignore` and append at the end:

```
# Debug snapshots
config.backup*.json
config.backup.json
*.bak
```

- [ ] **Step 3: Verify gitleaks is happy**

```bash
pre-commit run gitleaks --all-files
```

Expected: `Passed` (no secrets found in tracked files). If it reports a finding, inspect it — if it's a false positive, add it to `.gitleaks.toml` allowlist. If it's a real secret in a tracked file, rotate that credential immediately and remove it from history.

- [ ] **Step 4: Commit**

```bash
git add .gitleaks.toml .gitignore
git commit -m "chore: add gitleaks allowlist and expand .gitignore"
```

---

## Task 5: Delete stale debug files

**Files:**
- Delete: `config.backup-*.json` (8 files, untracked)
- Delete: `config.backup.json` (untracked)

- [ ] **Step 1: Confirm these files are untracked (not staged)**

```bash
git status --short | grep config.backup
```

Expected: all lines start with `??` (untracked). If any start with `M` or `A`, stop and investigate — do not delete staged/committed backup files.

- [ ] **Step 2: Delete the files**

```bash
rm config.backup*.json config.backup.json 2>/dev/null; echo "done"
```

On Windows (PowerShell):
```powershell
Remove-Item config.backup*.json, config.backup.json -ErrorAction SilentlyContinue
```

- [ ] **Step 3: Verify .gitignore now prevents future backups from appearing**

```bash
git status --short | grep config.backup
```

Expected: no output (files deleted AND pattern now in .gitignore so future ones won't show up as untracked).

- [ ] **Step 4: Commit .gitignore change (files themselves don't need a commit — they were never tracked)**

```bash
git add .gitignore
git status
```

The backup files should not appear in `git status` at all. If .gitignore was already committed in Task 4, this step is already done.

---

## Task 6: GitHub Actions — Python CI

**Files:**
- Create: `.github/workflows/python-ci.yml`

- [ ] **Step 1: Create the workflow directory and file**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Write the workflow**

```yaml
name: Python CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt ruff

      - name: Lint (ruff check)
        run: ruff check .

      - name: Format check (ruff format)
        run: ruff format --check .

      - name: Run tests
        run: pytest tests/ -v --ignore=tests/test_scraper.py
        env:
          TESTING: "true"
          FLASK_TESTING: "true"
```

Note: `test_scraper.py` is excluded because it requires a live Playwright browser. All other test files run against the Flask test client with a temporary SQLite DB.

- [ ] **Step 3: Commit and push**

```bash
git add .github/workflows/python-ci.yml
git commit -m "ci: add Python lint + test workflow"
git push
```

- [ ] **Step 4: Verify the workflow ran**

Open GitHub → repository → Actions tab. The `Python CI` workflow should appear. Green = done. If it fails, the most likely cause is a test that requires `config.json` — fix by mocking `load_config` in that test or adding a `TESTING` guard in the app startup code.

---

## Task 7: GitHub Actions — React CI

**Files:**
- Create: `.github/workflows/react-ci.yml`

- [ ] **Step 1: Check if package-lock.json exists (required for `npm ci`)**

```bash
ls mass-market-app/package-lock.json
```

If it doesn't exist:
```bash
cd mass-market-app && npm install && cd ..
git add mass-market-app/package-lock.json
git commit -m "chore: add package-lock.json"
```

- [ ] **Step 2: Write the workflow**

```yaml
name: React CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: mass-market-app

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: mass-market-app/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Lint
        run: npm run lint

      - name: Build
        run: npm run build
        env:
          VITE_API_URL: "http://localhost:5000"
          VITE_SUPABASE_URL: "https://placeholder.supabase.co"
          VITE_SUPABASE_ANON_KEY: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiJ9.placeholder"
          VITE_API_KEY: "ci-placeholder"
          VITE_DEV_AUTH: "false"
```

The placeholder Supabase values are intentional — `lib/supabase.js` already handles graceful null when unconfigured, so the build completes without real credentials.

- [ ] **Step 3: Commit and push**

```bash
git add .github/workflows/react-ci.yml
git commit -m "ci: add React lint + build workflow"
git push
```

- [ ] **Step 4: Verify on GitHub Actions**

Open GitHub → Actions → `React CI`. If the lint step fails, it means there are existing ESLint violations. Fix them locally with `cd mass-market-app && npm run lint` and commit the fixes before re-running.

---

## Self-Review

**Spec coverage check:**
- [x] pyproject.toml with ruff → Task 1
- [x] ruff violations fixed → Task 2
- [x] pre-commit hooks → Task 3
- [x] gitleaks → Tasks 3 + 4
- [x] .gitignore expansion → Task 4
- [x] debug file cleanup → Task 5
- [x] GitHub Actions Python → Task 6
- [x] GitHub Actions React → Task 7

**Placeholder scan:** No TBDs or TODOs in plan body.

**Type consistency:** No types defined across tasks — N/A.

**Risk:** The gitleaks scan in Task 3 may find real findings if any credentials were accidentally committed before the security hardening sprint (2026-04-25). The plan handles this: inspect each finding, rotate if real, add to allowlist if false positive.
