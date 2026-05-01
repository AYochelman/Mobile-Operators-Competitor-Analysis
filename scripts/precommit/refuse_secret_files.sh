#!/usr/bin/env bash
# Pre-commit hook: refuse to commit secret-shaped files.
# See .pre-commit-config.yaml.

set -euo pipefail

if git diff --cached --name-only | grep -E "(Recovery Codes|recovery_codes|\.pem$|\.key$|/secrets/|^config\.json$)" > /tmp/precommit_secret_match 2>&1; then
    echo "ERROR: Refusing to commit secret-shaped file(s):" >&2
    cat /tmp/precommit_secret_match >&2
    echo "" >&2
    echo "If this is intentional (you should rarely need this), use:" >&2
    echo "  git commit --no-verify" >&2
    exit 1
fi
