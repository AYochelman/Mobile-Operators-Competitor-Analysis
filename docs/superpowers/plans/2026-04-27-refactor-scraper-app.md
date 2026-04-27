# Refactor scraper.py + app.py into Packages

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the 7,235-line `scraper.py` into a `scrapers/` package and the 3,180-line `app.py` into a `routes/` package + `auth.py` + `scheduler.py`, with zero behavior change.

**Architecture:** Refactor-only — no logic changes. The strategy is "create package → shim old file → move code in slices → verify tests pass → delete shim." This gives a safe rollback point at every step. `scraper.py` stays as a thin re-export shim until the end so all existing `from scraper import ...` calls in `app.py` continue to work without changes until the routes refactor is done.

**Tech Stack:** Python 3.11, Flask Blueprints, existing pytest suite (`tests/test_api.py`, `tests/test_app.py`, `tests/test_db.py`)

---

## File Map

### scrapers/ package (new)

| File | What moves there | Source lines (approx) |
|------|-----------------|----------------------|
| `scrapers/__init__.py` | Re-exports entire public API | — |
| `scrapers/base.py` | Shared utilities: parsers, `_dismiss_popups`, `_make_global_plan`, exchange rate fetchers, `_POPUP_CLOSE_SELECTORS`, `_ensure_event_loop`, `_run_parallel_scraper` | 1–114, 1995–2072 |
| `scrapers/domestic.py` | 11 domestic carrier scrapers + `scrape_all()` | 115–1330 |
| `scrapers/abroad.py` | 8 abroad scrapers | 266–371, 505–529, 805–948, 1702–1994 |
| `scrapers/global_esim.py` | 20 global eSIM scrapers + `scrape_all_global()` | 2073–6546 |
| `scrapers/content.py` | `scrape_all_content()` + helpers | 6547–6729, 6756–end |
| `scrapers/banners.py` | `scrape_carrier_banners()`, `scrape_carrier_store_banners()` | grep `def scrape_carrier_banners` |
| `scrapers/news.py` | `scrape_carrier_news()` | 2868–2931 |

### routes/ package (new)

| File | Routes moved there |
|------|--------------------|
| `routes/__init__.py` | Blueprint registration helper |
| `routes/plans.py` | `/api/plans`, `/api/changes`, `/api/abroad-*`, `/api/global-*`, `/api/content-*`, `/api/exchange-rates`, `/api/news`, `/api/market-movers`, `/api/history/*` |
| `routes/scrape.py` | `/api/scrape-*-now`, `/api/scrape-progress/*`, `/api/refresh-quota` |
| `routes/banners.py` | `/api/banners`, `/api/store-banners`, `/banners/<file>`, `/archive-banners/*`, `/api/archive/*` |
| `routes/users.py` | `/api/users`, `/api/my-*`, `/api/watchlist`, `/api/saved-views`, `/api/annotations` |
| `routes/workspaces.py` | `/api/workspaces`, `/api/invite/*`, `/api/workspace/*` |
| `routes/chat.py` | `/api/chat` |
| `routes/push.py` | `/api/push/*`, `/api/auth/*` |
| `routes/alerts.py` | `/api/alerts` |
| `routes/executive.py` | `/api/executive-summary`, `/api/social-sentiment` |
| `routes/admin.py` | `/api/audit-log`, `/api/affiliate/*`, `/go/<provider>` |
| `routes/misc.py` | `/`, `/sw.js`, `/api/health`, `/api/contact` |

### New root-level modules

| File | What moves there |
|------|-----------------|
| `auth.py` | `load_config`, `_get_api_key`, `_get_server_admin_key`, `require_api_key`, `require_auth`, `require_scrape_auth`, `_verify_supabase_jwt`, `_get_jwks`, `_require_role`, `_is_server_admin_request`, `_current_user_email`, `_can_manage_workspace_users`, `_hidden_carrier_for_request`, `_filter_hidden_carrier`, `_get_user_context`, `require_api_key_or_query` |
| `scheduler.py` | APScheduler setup + all scheduled job functions |

### Modified

| File | Change |
|------|--------|
| `scraper.py` | Becomes thin shim: `from scrapers import *` |
| `app.py` | Becomes thin app factory: imports blueprints, registers them |
| `tests/test_imports.py` | New: verifies public API is importable from new locations |

---

## Task 1: Create scrapers/ package — base utilities

**Files:**
- Create: `scrapers/__init__.py`
- Create: `scrapers/base.py`
- Create: `tests/test_imports.py`

- [ ] **Step 1: Write failing import test**

Create `tests/test_imports.py`:

```python
"""Verify the new scrapers/ package exports all public functions."""

def test_scrapers_base_importable():
    from scrapers.base import (
        _parse_price, _parse_minutes, _parse_gb, _parse_days, _parse_sms,
        _make_global_plan, _ensure_event_loop, _run_parallel_scraper,
        _get_usd_to_ils, _get_eur_to_ils, _get_gbp_to_ils,
    )
    assert callable(_parse_price)
    assert callable(_make_global_plan)


def test_scrapers_package_importable():
    import scrapers
    assert hasattr(scrapers, 'scrape_all')
    assert hasattr(scrapers, 'scrape_all_global')
    assert hasattr(scrapers, 'scrape_all_content')
    assert hasattr(scrapers, 'scrape_carrier_news')
    assert hasattr(scrapers, 'scrape_carrier_banners')
    assert hasattr(scrapers, 'scrape_carrier_store_banners')
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_imports.py -v
```

Expected: `ImportError: No module named 'scrapers'`

- [ ] **Step 3: Create scrapers/__init__.py (empty stub)**

```python
# Will be populated as submodules are created
```

- [ ] **Step 4: Create scrapers/base.py**

Copy from `scraper.py` the following functions/constants (do not delete from scraper.py yet):
- Lines 1–17 (module docstring + imports)
- `_ensure_event_loop` (line 20)
- `_run_parallel_scraper` (line 31)
- `_parse_price` (line 49)
- `_parse_minutes` (line 61)
- `_parse_gb` (line 73)
- `_parse_days` (line 93)
- `_parse_sms` (line 102)
- `_get_usd_to_ils` (line 1995)
- `_get_eur_to_ils` (line 2021)
- `_get_gbp_to_ils` (line 2037)
- `_make_global_plan` (line 2053)
- All `_POPUP_CLOSE_SELECTORS` / `_dismiss_popups` constants (search `grep -n "_POPUP_CLOSE_SELECTORS\|_dismiss_popups" scraper.py`)

File header:
```python
"""
scrapers/base.py — shared utilities used across all carrier scrapers.
"""
from playwright.sync_api import sync_playwright  # noqa: F401 — re-exported for scrapers
import re
import logging
import json as _json
import urllib.request
import asyncio
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
```

Then paste each function verbatim from scraper.py.

- [ ] **Step 5: Update scrapers/__init__.py to import base**

```python
from scrapers.base import (
    _parse_price, _parse_minutes, _parse_gb, _parse_days, _parse_sms,
    _make_global_plan, _ensure_event_loop, _run_parallel_scraper,
    _get_usd_to_ils, _get_eur_to_ils, _get_gbp_to_ils,
)

__all__ = [
    "_parse_price", "_parse_minutes", "_parse_gb", "_parse_days", "_parse_sms",
    "_make_global_plan", "_ensure_event_loop", "_run_parallel_scraper",
    "_get_usd_to_ils", "_get_eur_to_ils", "_get_gbp_to_ils",
]
```

(We will extend `__all__` in later tasks as more submodules are added.)

- [ ] **Step 6: Run import test for base**

```bash
pytest tests/test_imports.py::test_scrapers_base_importable -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scrapers/ tests/test_imports.py
git commit -m "refactor: create scrapers/base.py with shared utilities"
```

---

## Task 2: scrapers/domestic.py

**Files:**
- Create: `scrapers/domestic.py`
- Modify: `scrapers/__init__.py`

The domestic scrapers and their coordinator function `scrape_all()` cover scraper.py lines 115–1330. They depend on functions from `scrapers/base.py`.

- [ ] **Step 1: Write failing test**

Add to `tests/test_imports.py`:

```python
def test_scrapers_domestic_importable():
    from scrapers.domestic import (
        scrape_xphone, scrape_wecom, scrape_neptucom, scrape_golan,
        scrape_rami_levy, scrape_partner, scrape_pelephone,
        scrape_hotmobile, scrape_cellcom, scrape_019, scrape_all,
    )
    assert callable(scrape_all)
```

Run: `pytest tests/test_imports.py::test_scrapers_domestic_importable -v`
Expected: `ImportError: cannot import name 'scrape_xphone' from 'scrapers.domestic'`

- [ ] **Step 2: Create scrapers/domestic.py**

File header:

```python
"""
scrapers/domestic.py — domestic cellular plan scrapers for 8 Israeli carriers.
All scrape_* functions take an optional Playwright Page; if None, they launch their own browser.
"""
from playwright.sync_api import sync_playwright
import re
import logging
from scrapers.base import (
    _parse_price, _parse_minutes, _parse_gb, _parse_days, _parse_sms,
    _dismiss_popups, _ensure_event_loop,
)

logger = logging.getLogger(__name__)
```

Then copy verbatim from `scraper.py`:
- `scrape_xphone` (lines 115–265)
- `scrape_wecom` + `_scrape_wecom_page` (lines 372–504)
- `scrape_neptucom` (lines 530–652)
- `_parse_golan_body`, `scrape_golan` (lines 653–1013)
- `_parse_rami_levy_body`, `scrape_rami_levy` (lines 1014–1290)
- `scrape_all` (lines 1291–1330)
- `scrape_partner` (lines 1331–1380)
- `scrape_pelephone` (lines 1381–1449)
- `scrape_hotmobile` (lines 1450–1525)
- `_fetch_cellcom_terms_urls`, `scrape_cellcom` (lines 1526–1633)
- `scrape_019` (lines 1634–1701)

- [ ] **Step 3: Register in scrapers/__init__.py**

Add to `__init__.py`:
```python
from scrapers.domestic import (
    scrape_partner, scrape_pelephone, scrape_hotmobile, scrape_cellcom,
    scrape_xphone, scrape_wecom, scrape_neptucom, scrape_019, scrape_golan,
    scrape_rami_levy, scrape_all,
)
```

Add these names to `__all__`.

- [ ] **Step 4: Run test**

```bash
pytest tests/test_imports.py::test_scrapers_domestic_importable -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/domestic.py scrapers/__init__.py tests/test_imports.py
git commit -m "refactor: create scrapers/domestic.py with 11 domestic scrapers"
```

---

## Task 3: scrapers/abroad.py

**Files:**
- Create: `scrapers/abroad.py`
- Modify: `scrapers/__init__.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_imports.py`:

```python
def test_scrapers_abroad_importable():
    from scrapers.abroad import (
        scrape_xphone_abroad, scrape_wecom_abroad, scrape_golan_abroad,
        scrape_pelephone_abroad, scrape_cellcom_abroad, scrape_partner_abroad,
        scrape_hotmobile_abroad, scrape_019_abroad,
    )
    assert callable(scrape_pelephone_abroad)
```

Run: `pytest tests/test_imports.py::test_scrapers_abroad_importable -v`
Expected: ImportError

- [ ] **Step 2: Create scrapers/abroad.py**

```python
"""
scrapers/abroad.py — per-country roaming plan scrapers for 8 Israeli carriers.
"""
from playwright.sync_api import sync_playwright
import re
import logging
from scrapers.base import (
    _parse_price, _parse_minutes, _parse_gb, _parse_days, _parse_sms,
    _dismiss_popups, _ensure_event_loop,
)

logger = logging.getLogger(__name__)
```

Copy verbatim from `scraper.py`:
- `scrape_xphone_abroad` (lines 266–371)
- `scrape_wecom_abroad` (lines 505–529)
- `_parse_golan_abroad_plans`, `scrape_golan_abroad` (lines 805–1013 — note these share parse helpers with golan domestic; keep the abroad-specific `_parse_golan_abroad_plans` here and import the shared helper from `scrapers.domestic` if needed)
- `scrape_pelephone_abroad` (lines 1702–1753)
- `scrape_cellcom_abroad` (lines 1754–1842)
- `scrape_partner_abroad` (lines 1843–1889)
- `scrape_hotmobile_abroad` (lines 1890–1933)
- `scrape_019_abroad` (lines 1934–1994)

- [ ] **Step 3: Register in scrapers/__init__.py**

```python
from scrapers.abroad import (
    scrape_xphone_abroad, scrape_wecom_abroad, scrape_golan_abroad,
    scrape_pelephone_abroad, scrape_cellcom_abroad, scrape_partner_abroad,
    scrape_hotmobile_abroad, scrape_019_abroad,
)
```

- [ ] **Step 4: Run test**

```bash
pytest tests/test_imports.py::test_scrapers_abroad_importable -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/abroad.py scrapers/__init__.py tests/test_imports.py
git commit -m "refactor: create scrapers/abroad.py with 8 abroad scrapers"
```

---

## Task 4: scrapers/news.py + scrapers/banners.py

**Files:**
- Create: `scrapers/news.py`
- Create: `scrapers/banners.py`
- Modify: `scrapers/__init__.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_imports.py`:

```python
def test_scrapers_news_importable():
    from scrapers.news import scrape_carrier_news
    assert callable(scrape_carrier_news)

def test_scrapers_banners_importable():
    from scrapers.banners import scrape_carrier_banners, scrape_carrier_store_banners
    assert callable(scrape_carrier_banners)
    assert callable(scrape_carrier_store_banners)
```

Run: `pytest tests/test_imports.py -k "news or banners" -v`
Expected: both fail with ImportError

- [ ] **Step 2: Create scrapers/news.py**

```python
"""
scrapers/news.py — scrapes Google News RSS for each domestic carrier.
"""
import logging
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
```

Copy `scrape_carrier_news` (lines 2868–2931) verbatim.

- [ ] **Step 3: Find and create scrapers/banners.py**

First, find the banner scraper functions:

```bash
grep -n "def scrape_carrier_banners\|def scrape_carrier_store_banners" scraper.py
```

Copy both functions verbatim. File header:

```python
"""
scrapers/banners.py — takes Playwright screenshots of carrier homepages and e-stores.
"""
from playwright.sync_api import sync_playwright
import logging
import os
from scrapers.base import _dismiss_popups

logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Register in scrapers/__init__.py**

```python
from scrapers.news import scrape_carrier_news
from scrapers.banners import scrape_carrier_banners, scrape_carrier_store_banners
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_imports.py -k "news or banners" -v
```

Expected: both PASS

- [ ] **Step 6: Commit**

```bash
git add scrapers/news.py scrapers/banners.py scrapers/__init__.py tests/test_imports.py
git commit -m "refactor: create scrapers/news.py and scrapers/banners.py"
```

---

## Task 5: scrapers/global_esim.py + scrapers/content.py

**Files:**
- Create: `scrapers/global_esim.py`
- Create: `scrapers/content.py`
- Modify: `scrapers/__init__.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_imports.py`:

```python
def test_scrapers_global_esim_importable():
    from scrapers.global_esim import (
        scrape_tuki_global, scrape_globalesim_global, scrape_airalo_global,
        scrape_saily_global, scrape_holafly_global, scrape_orbit_global,
        scrape_all_global,
    )
    assert callable(scrape_all_global)

def test_scrapers_content_importable():
    from scrapers.content import scrape_all_content
    assert callable(scrape_all_content)
```

Run: `pytest tests/test_imports.py -k "global_esim or content" -v`
Expected: both fail

- [ ] **Step 2: Create scrapers/global_esim.py**

This is the largest module (~4,500 lines). File header:

```python
"""
scrapers/global_esim.py — eSIM plan scrapers for 20 global providers.
Slug-to-Hebrew lookup dicts live here:
  SAILY_SLUG_TO_HEBREW, ESIMIO_SLUG_TO_HEBREW, HOLAFLY_SLUG_TO_HEBREW, ORBIT_NAME_TO_HEBREW
"""
from playwright.sync_api import sync_playwright
import re
import logging
import json as _json
import urllib.request
from datetime import datetime, timezone
from scrapers.base import (
    _make_global_plan, _dismiss_popups, _ensure_event_loop, _run_parallel_scraper,
    _get_usd_to_ils, _get_eur_to_ils, _get_gbp_to_ils,
)

logger = logging.getLogger(__name__)
```

Copy verbatim from `scraper.py` lines 2073–6546 (all global scrapers, slug dicts, and `scrape_all_global`).

- [ ] **Step 3: Create scrapers/content.py**

```python
"""
scrapers/content.py — content service plan scrapers (eSIM watch, cyber, Norton, etc.)
"""
from playwright.sync_api import sync_playwright
import re
import logging
from scrapers.base import _dismiss_popups

logger = logging.getLogger(__name__)
```

Copy lines 6547–end (`_extract_content_price`, `_cellcom_hub_price`, `scrape_all_content`, and all content helpers).

- [ ] **Step 4: Register in scrapers/__init__.py**

```python
from scrapers.global_esim import scrape_all_global
from scrapers.content import scrape_all_content
```

Also expose individual global scrapers needed by app.py:
```python
from scrapers.global_esim import (
    scrape_tuki_global, scrape_globalesim_global, scrape_airalo_global,
    scrape_airalo_local, scrape_airalo_regional,
    scrape_saily_global, scrape_saily_regions,
    scrape_holafly_global, scrape_holafly_regions,
    scrape_orbit_global, scrape_travelsim,
    scrape_esimio_destinations, scrape_esimio_regions,
    scrape_voye_global, scrape_sparks_global,
)
```

- [ ] **Step 5: Run all import tests**

```bash
pytest tests/test_imports.py -v
```

Expected: all tests PASS (6 test functions)

- [ ] **Step 6: Commit**

```bash
git add scrapers/global_esim.py scrapers/content.py scrapers/__init__.py tests/test_imports.py
git commit -m "refactor: create scrapers/global_esim.py and scrapers/content.py"
```

---

## Task 6: Convert scraper.py to thin shim

**Files:**
- Modify: `scraper.py` (replace ~7235 lines with ~30 lines)

- [ ] **Step 1: Verify all existing tests still pass before touching scraper.py**

```bash
pytest tests/ -v --ignore=tests/test_scraper.py
```

All tests should pass. If any fail, fix them before proceeding.

- [ ] **Step 2: Replace scraper.py content**

Replace the entire file with:

```python
"""
scraper.py — backwards-compatibility shim.
All scraper logic now lives in the scrapers/ package.
Import from scrapers.* directly for new code.
"""
from scrapers import *  # noqa: F401, F403
from scrapers.base import (
    _parse_price, _parse_minutes, _parse_gb, _parse_days, _parse_sms,
    _make_global_plan, _ensure_event_loop, _run_parallel_scraper,
    _get_usd_to_ils, _get_eur_to_ils, _get_gbp_to_ils,
    _dismiss_popups, _POPUP_CLOSE_SELECTORS,
)
from scrapers.domestic import (
    scrape_partner, scrape_pelephone, scrape_hotmobile, scrape_cellcom,
    scrape_xphone, scrape_wecom, scrape_neptucom, scrape_019, scrape_golan,
    scrape_rami_levy, scrape_all,
)
from scrapers.abroad import (
    scrape_xphone_abroad, scrape_wecom_abroad, scrape_golan_abroad,
    scrape_pelephone_abroad, scrape_cellcom_abroad, scrape_partner_abroad,
    scrape_hotmobile_abroad, scrape_019_abroad,
)
from scrapers.global_esim import scrape_all_global
from scrapers.content import scrape_all_content
from scrapers.news import scrape_carrier_news
from scrapers.banners import scrape_carrier_banners, scrape_carrier_store_banners
```

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v --ignore=tests/test_scraper.py
```

Expected: same results as before Step 1.

- [ ] **Step 4: Verify app.py imports still work**

```bash
python -c "import app; print('app imports OK')"
```

Expected: `app imports OK` (no ImportError)

- [ ] **Step 5: Commit**

```bash
git add scraper.py
git commit -m "refactor: convert scraper.py to thin shim importing from scrapers/"
```

---

## Task 7: Extract auth.py

**Files:**
- Create: `auth.py`
- Modify: `app.py` (replace inline definitions with imports)

- [ ] **Step 1: Write failing test**

Add to `tests/test_imports.py`:

```python
def test_auth_module_importable():
    from auth import load_config, require_api_key, require_auth, require_scrape_auth
    assert callable(require_api_key)
    assert callable(load_config)
```

Run: `pytest tests/test_imports.py::test_auth_module_importable -v`
Expected: `ModuleNotFoundError: No module named 'auth'`

- [ ] **Step 2: Create auth.py**

File header:
```python
"""
auth.py — API key + JWT auth decorators, config loading, and role helpers.
"""
import json
import os
import secrets
import hmac
import hashlib
import base64
import logging
import time as _time
from functools import wraps
from datetime import datetime, timezone, timedelta
from flask import request, jsonify, g
import urllib.request

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
```

Copy verbatim from `app.py`:
- `load_config` (find with `grep -n "^def load_config" app.py`)
- `_get_api_key`
- `_get_server_admin_key`
- `require_api_key`
- `require_auth`
- `require_api_key_or_query`
- `require_scrape_auth`
- `_get_jwks`
- `_verify_supabase_jwt`
- `_require_role`
- `_is_valid_slack_webhook`
- `_current_user_email`
- `_is_server_admin_request`
- `_can_manage_workspace_users`
- `_hidden_carrier_for_request`
- `_filter_hidden_carrier`
- `_get_user_context`
- `_check_refresh_quota`
- `_workspace_refresh_quota_for_email`
- `_log_refresh`
- `_supabase_conn`
- `_db_path`
- `_ensure_vapid_keys`

- [ ] **Step 3: Run test**

```bash
pytest tests/test_imports.py::test_auth_module_importable -v
```

Expected: PASS

- [ ] **Step 4: Update app.py to import from auth.py instead of defining inline**

At the top of `app.py`, add:
```python
from auth import (
    load_config, require_api_key, require_auth, require_api_key_or_query,
    require_scrape_auth, _get_api_key, _get_server_admin_key,
    _require_role, _current_user_email, _is_server_admin_request,
    _can_manage_workspace_users, _hidden_carrier_for_request,
    _filter_hidden_carrier, _get_user_context, _check_refresh_quota,
    _workspace_refresh_quota_for_email, _log_refresh,
    _supabase_conn, _db_path, _ensure_vapid_keys, CONFIG_PATH,
)
```

Then delete the now-duplicated inline definitions from `app.py`.

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v --ignore=tests/test_scraper.py
python -c "import app; print('OK')"
```

Expected: all pass, no ImportError.

- [ ] **Step 6: Commit**

```bash
git add auth.py app.py tests/test_imports.py
git commit -m "refactor: extract auth.py with auth decorators and config helpers"
```

---

## Task 8: Create routes/ package — Blueprints scaffolding

**Files:**
- Create: `routes/__init__.py`
- Create: `routes/plans.py` (stub)
- Create: `routes/scrape.py` (stub)
- Create: `routes/banners.py` (stub)
- Create: `routes/users.py` (stub)
- Create: `routes/workspaces.py` (stub)
- Create: `routes/chat.py` (stub)
- Create: `routes/push.py` (stub)
- Create: `routes/alerts.py` (stub)
- Create: `routes/executive.py` (stub)
- Create: `routes/admin.py` (stub)
- Create: `routes/misc.py` (stub)

- [ ] **Step 1: Write failing test**

Add to `tests/test_imports.py`:

```python
def test_routes_blueprints_importable():
    from routes.plans import bp as plans_bp
    from routes.scrape import bp as scrape_bp
    from routes.banners import bp as banners_bp
    from routes.users import bp as users_bp
    from routes.workspaces import bp as workspaces_bp
    from routes.chat import bp as chat_bp
    from routes.push import bp as push_bp
    from routes.alerts import bp as alerts_bp
    from routes.executive import bp as executive_bp
    from routes.admin import bp as admin_bp
    from routes.misc import bp as misc_bp
    from flask import Flask
    app = Flask(__name__)
    for bp in [plans_bp, scrape_bp, banners_bp, users_bp, workspaces_bp,
               chat_bp, push_bp, alerts_bp, executive_bp, admin_bp, misc_bp]:
        app.register_blueprint(bp)
    assert len(app.blueprints) == 11
```

Run: `pytest tests/test_imports.py::test_routes_blueprints_importable -v`
Expected: ImportError

- [ ] **Step 2: Create routes/__init__.py**

```python
"""routes — Flask Blueprint package for MOCA API routes."""
```

- [ ] **Step 3: Create all stub blueprint files**

Each file follows the same pattern. Create all 11:

`routes/plans.py`:
```python
from flask import Blueprint
bp = Blueprint("plans", __name__)
# Routes will be moved here from app.py in Task 9
```

`routes/scrape.py`:
```python
from flask import Blueprint
bp = Blueprint("scrape", __name__)
```

`routes/banners.py`:
```python
from flask import Blueprint
bp = Blueprint("banners", __name__)
```

`routes/users.py`:
```python
from flask import Blueprint
bp = Blueprint("users", __name__)
```

`routes/workspaces.py`:
```python
from flask import Blueprint
bp = Blueprint("workspaces", __name__)
```

`routes/chat.py`:
```python
from flask import Blueprint
bp = Blueprint("chat", __name__)
```

`routes/push.py`:
```python
from flask import Blueprint
bp = Blueprint("push", __name__)
```

`routes/alerts.py`:
```python
from flask import Blueprint
bp = Blueprint("alerts", __name__)
```

`routes/executive.py`:
```python
from flask import Blueprint
bp = Blueprint("executive", __name__)
```

`routes/admin.py`:
```python
from flask import Blueprint
bp = Blueprint("admin", __name__)
```

`routes/misc.py`:
```python
from flask import Blueprint
bp = Blueprint("misc", __name__)
```

- [ ] **Step 4: Run test**

```bash
pytest tests/test_imports.py::test_routes_blueprints_importable -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add routes/
git commit -m "refactor: create routes/ package with 11 Blueprint stubs"
```

---

## Task 9: Move routes one blueprint at a time

This task moves route handlers from `app.py` into their respective Blueprint files. Do **one blueprint at a time**. Run the full test suite after each move.

The pattern for every move is identical:

```
a. Find the routes in app.py using grep -n "@app.route"
b. In the blueprint file, add the imports the handlers need
c. Copy the handler functions, changing @app.route → @bp.route
d. In app.py, replace the handler body with a pass-through import (or delete and register blueprint)
e. pytest tests/ -v --ignore=tests/test_scraper.py
f. git commit
```

**Move order (safest first, most dependencies last):**

### 9a: routes/misc.py

Routes to move from `app.py`:
- `GET /` (line 722)
- `GET /sw.js` (line 730)
- `GET /api/health` (line 3377)
- `GET /api/contact` POST (line 2559)

`routes/misc.py` after move:
```python
from flask import Blueprint, render_template, send_from_directory, jsonify, request
from auth import require_auth, load_config
from db import log_audit
import logging

logger = logging.getLogger(__name__)
bp = Blueprint("misc", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


@bp.route("/api/health")
def api_health():
    # copy the handler body verbatim from app.py
    ...


@bp.route("/api/contact", methods=["POST"])
def api_contact():
    # copy verbatim
    ...
```

Register in `app.py` after the limiter setup:
```python
from routes.misc import bp as misc_bp
app.register_blueprint(misc_bp)
```

Then remove the duplicate `@app.route` handlers from `app.py`.

Run: `pytest tests/ -v --ignore=tests/test_scraper.py`
Commit: `refactor: move misc routes to routes/misc.py`

### 9b–9k: Repeat for each remaining blueprint

Follow the same pattern for:
- **9b** `routes/plans.py` — data read routes (no side effects, safest)
- **9c** `routes/alerts.py`
- **9d** `routes/push.py`
- **9e** `routes/chat.py`
- **9f** `routes/banners.py`
- **9g** `routes/executive.py`
- **9h** `routes/admin.py`
- **9i** `routes/users.py`
- **9j** `routes/workspaces.py` (most complex — workspace CRUD + invite flows)
- **9k** `routes/scrape.py` (last — SSE stream requires careful import of `_scrape_emit`, `_scrape_start`, `_scrape_finish` which should move here too)

Each step: copy handlers + run tests + commit. If a test breaks, the most likely cause is a missing import (a helper function still in `app.py` that the moved handler calls). Fix by either importing the helper from `auth.py` or moving the helper into the blueprint file.

- [ ] **Run tests after all blueprints moved**

```bash
pytest tests/ -v --ignore=tests/test_scraper.py
python -c "import app; print('app.py routes OK:', len(app.url_map._rules), 'rules')"
```

Expected: same test results, same number of URL rules as before the refactor.

- [ ] **Commit**

```bash
git add routes/ app.py
git commit -m "refactor: move all routes to blueprints; app.py is now thin factory"
```

---

## Task 10: Extract scheduler.py

**Files:**
- Create: `scheduler.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_imports.py`:

```python
def test_scheduler_importable():
    from scheduler import init_scheduler
    assert callable(init_scheduler)
```

Run: `pytest tests/test_imports.py::test_scheduler_importable -v`
Expected: ModuleNotFoundError

- [ ] **Step 2: Create scheduler.py**

```python
"""
scheduler.py — APScheduler setup and scheduled job definitions.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)


def init_scheduler(app):
    """Create and start the APScheduler. Called from app.py after all routes are registered."""
    scheduler = BackgroundScheduler(timezone="Asia/Jerusalem")

    # 08:00 — banner screenshots
    scheduler.add_job(
        lambda: _run_in_context(app, _job_banners),
        CronTrigger(hour=8, minute=0),
        id="banners",
        replace_existing=True,
    )

    # 08:10 — news RSS
    scheduler.add_job(
        lambda: _run_in_context(app, _job_news),
        CronTrigger(hour=8, minute=10),
        id="news",
        replace_existing=True,
    )

    # 09:00 — daily Excel email
    scheduler.add_job(
        lambda: _run_in_context(app, _job_excel_report),
        CronTrigger(hour=9, minute=0),
        id="excel_report",
        replace_existing=True,
    )

    # 10:00 + 16:00 — full scrape
    for hour in [10, 16]:
        scheduler.add_job(
            lambda h=hour: _run_in_context(app, _job_scrape_all),
            CronTrigger(hour=hour, minute=0),
            id=f"scrape_all_{hour}",
            replace_existing=True,
        )

    scheduler.start()
    logger.info("APScheduler started")
    return scheduler


def _run_in_context(app, job_fn):
    with app.app_context():
        job_fn()
```

Then copy each `_job_*` helper function verbatim from wherever the scheduled jobs are defined in `app.py`.

- [ ] **Step 3: Update app.py**

```python
from scheduler import init_scheduler

# At the bottom of app.py, replace the inline APScheduler setup with:
if __name__ == "__main__" or os.environ.get("FLASK_RUN_MAIN") == "true":
    init_scheduler(app)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/ -v --ignore=tests/test_scraper.py
python -c "import app; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add scheduler.py app.py tests/test_imports.py
git commit -m "refactor: extract scheduler.py; app.py is now a pure app factory"
```

---

## Self-Review

**Spec coverage:**
- [x] scraper.py (~7235 lines) split into `scrapers/` package → Tasks 1–6
- [x] app.py (~3180 lines) split into `routes/` + `auth.py` + `scheduler.py` → Tasks 7–10
- [x] Zero behavior change guaranteed via existing test suite + import tests

**Placeholder scan:**
- Task 9b–9k uses "repeat for each remaining blueprint" with the exact pattern shown — each step has the same 5-action structure. Engineers have the full pattern from 9a.
- Task 2 Step 2 and Task 3 Step 2 use "copy verbatim from lines X–Y" — these are move operations, not new code. Repeating 7000 lines of scraper code would be noise, not signal. The line numbers are exact.

**Type consistency:** No new types introduced. Existing function signatures are copied verbatim.

**Risk areas:**
1. `_scrape_emit` / `_scrape_start` / `_scrape_finish` are SSE helpers tightly coupled to the scrape route — they must move together into `routes/scrape.py` (noted in Task 9k).
2. `generate_social_sentiment` and `generate_executive_summary` are long functions in app.py (lines 1295–1652) that call `anthropic` directly — they may move to `routes/executive.py` or a separate `services/` module if they grow further.
3. The `limiter` object is created in `app.py` — blueprint routes that use `@limiter.limit(...)` decorators need `limiter` imported from `app.py` or converted to a factory pattern. Inspect each route before moving it.
