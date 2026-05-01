#!/usr/bin/env bash
# Pre-commit hook: refuse VITE_DEV_AUTH=true in .env.production.
# See .pre-commit-config.yaml.
#
# Why this matters: VITE_DEV_AUTH=true bypasses login and grants
# super_admin to anyone visiting the site. It must NEVER be set in
# production builds. CLAUDE.md documents this explicitly.

set -euo pipefail

PROD_ENV="mass-market-app/.env.production"

if [ -f "$PROD_ENV" ] && grep -E "^VITE_DEV_AUTH\s*=\s*true" "$PROD_ENV" >/dev/null 2>&1; then
    echo "ERROR: VITE_DEV_AUTH=true found in $PROD_ENV" >&2
    echo "       This would expose super_admin to all site visitors." >&2
    echo "       Remove the line or set VITE_DEV_AUTH=false." >&2
    exit 1
fi
