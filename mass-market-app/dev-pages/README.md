# dev-pages/ - operator-only HTML pages (NOT deployed)

Moved out of `public/` on 2026-09-11 during the privacy/accessibility audit:

- `diag.html` - dumps every `localStorage` key (including the auth token prefix and the
  Supabase session) and offers a "clear everything" button. Useful when a PWA cache goes
  stale, dangerous as a public URL.
- `preview-logo.html` - internal logo preview that hot-links Google's favicon service.

To use one locally, copy it into `public/` temporarily (do not commit) or open it directly
in a browser via `file://`.
