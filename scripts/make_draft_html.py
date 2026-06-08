# -*- coding: utf-8 -*-
"""Write the welcome email HTML (with the HOSTED hero URL) for a Gmail draft.

Usage: python scripts/make_draft_html.py [workspace] [role]
Output: docs/email/welcome-draft.html
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from notifier import _build_welcome_html, _WELCOME_HERO_URL  # noqa: E402

workspace = sys.argv[1] if len(sys.argv) > 1 else "סלקום"
role = sys.argv[2] if len(sys.argv) > 2 else "admin"
role_he = "מנהל" if role == "admin" else "צופה"

html = _build_welcome_html(
    workspace_name=workspace, role_he=role_he,
    hero_img_url=_WELCOME_HERO_URL, app_url="https://mocaintel.com",
    primary="#5c3317", secondary="#a08060",
)
out = os.path.join(ROOT, "docs", "email", "welcome-draft.html")
with open(out, "w", encoding="utf-8") as fh:
    fh.write(html)
print(f"wrote {out}  ({len(html)} chars)")
