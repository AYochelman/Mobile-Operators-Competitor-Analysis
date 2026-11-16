# Agentic readiness: lucent-kulfi-f037ad.netlify.app (2026-11-16)
Lighthouse Agentic Browsing: not computed (PSI HTTP 429 daily quota, mobile and desktop; no API key). Fraction unavailable.
Agent-UX heuristic (separate from Lighthouse): 100 complete for /esim-deals (176 nodes, 13 interactive, 0 unnamed, 5 landmarks) and /esim/thailand/ (348 nodes, 31 links, 0 unnamed, 4 landmarks). Heuristic is structural only; it does not prove the destination picker is operable.
Access: training/search/user-triggered all fall to User-agent * Allow: / (intentional, commented in robots.txt). /go/ disallowed. No Content-Signal.
Findings
1. P1 matters now: catch-all returns 200 text/html for unknown paths (soft 404), incl /.well-known/* and /index.md. Fix: netlify.toml/_redirects must not rewrite unknown paths to index.html with 200 except the specific SPA routes; add a 404.html. Also hurts Lighthouse llms-txt/ard-schema and Google soft-404.
2. P2 matters now: /esim-deals body is an empty div#root shell without JS (words_without_js 1106 was measured on / only). Non-JS fetchers (many AI crawlers) see no prices on it. Static /esim/<slug>/ pages cover this; link them from llms.txt and /esim-deals prerender noscript summary.
3. P2: verify picker/buy links by rendered tree: buy links are plain anchors (11 links on /esim-deals, 31 on thailand), 1 button on /esim-deals. Only 1 button means picker is probably a link list or custom control; confirm it has role combobox/listbox or native select with label. Not verified.
4. P3 speculative: llms.txt passes (2346 bytes, llms-full 200); Google ignores it. Info: H2 sections without links.
5. P3 speculative: Content-Signal, Markdown negotiation, ai-catalog.json, WebMCP (0 registerTool, no navigator.modelContext), agent-card, ucp: all absent. Opportunities, drafts/proposals as of 2026-09-23 vendor matrix; no proven ranking/citation effect.
Matters today: real 404s, server-rendered content, labelled links, robots policy. Everything else is optional.
