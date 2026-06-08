# -*- coding: utf-8 -*-
"""Send a sample MOCA welcome email via the real production path.

Calls notifier.send_welcome_email(...) exactly as app.py does on workspace
assignment / invite acceptance -- so this is a faithful end-to-end test
(HTML + inline CID hero image + plain-text fallback, via SendGrid).

Usage:
  python scripts/send_welcome_sample.py [to_email] [workspace] [role]
Defaults: alon.yoch@gmail.com / "סלקום" / admin
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from notifier import send_welcome_email  # noqa: E402


def main():
    to_email = sys.argv[1] if len(sys.argv) > 1 else "alon.yoch@gmail.com"
    workspace = sys.argv[2] if len(sys.argv) > 2 else "סלקום"
    role = sys.argv[3] if len(sys.argv) > 3 else "admin"

    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as fh:
        config = json.load(fh)
    if not (config.get("sendgrid_api_key") and config.get("email_sender")):
        print("ERROR: sendgrid_api_key / email_sender missing in config.json")
        return 1

    ok = send_welcome_email(to_email, workspace, role, config)
    if ok:
        print(f"OK — welcome email sent to {to_email} (inline CID hero).")
        return 0
    print(f"FAILED — send_welcome_email returned False for {to_email} "
          f"(check the logged SendGrid status above; e.g. credits/quota).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
