---
name: social-publish
description: >-
  Pre-publish pipeline for EVERY MOCA social post, reel, carousel, or video
  (Facebook, Instagram, TikTok). Use whenever the user drafts, schedules, uploads,
  or asks to prepare any social content, caption, or tagged link - even a casual
  "אני מעלה פוסט/סרטון" or "תכין לי נוסח". Runs the BiDi line-start lint, bans
  em-dashes, builds correctly-tagged attribution links (utm_source/utm_campaign -
  never src=esim), enforces video safe zones, proactively suggests the optimal
  posting window, and keeps the FB content calendar in sync.
---

# Social Publish - the MOCA pre-publish checklist

Every one of these rules exists because a real post already went wrong: a Hebrew
line opening with "MOCA" rendered scrambled on Facebook, a TikTok end-card URL got
covered by the UI, and `src=esim` links earned zero attribution. Run the full
checklist on every piece of content before it ships - and when the user merely says
he's about to upload something, run it proactively.

## 1. BiDi lint - every line opens with a Hebrew word

Facebook/Instagram set each line's direction by its **first strong character**. A line
that contains Hebrew but opens with a Latin word or `#hashtag` (MOCA / 5GB / #eSIM)
renders its Hebrew scrambled. This applies to the hashtag line too. English
mid-line (eSIM, MOCA) is fine. Prefer `18 ש"ח` over `₪18` - a currency sign glued to
a number can flip the line.

The canonical lint already exists - reuse it instead of eyeballing:

```bash
cd "D:\השוואת MASS MARKET" && PYTHONIOENCODING=utf-8 python -c "
import sys; sys.path.insert(0, 'scripts')
from fb_post_reminder import _bidi_problems
body = open('draft.txt', encoding='utf-8').read()  # or paste the draft inline
probs = _bidi_problems(body)
print('\n'.join(probs) if probs else 'BiDi OK')
"
```

Fix every flagged line by moving a Hebrew word to the front (e.g. `#eSIM לחו"ל` →
`ל-eSIM# בחו"ל` or open with `חבילות eSIM ...`).

## 2. Copy rules

- **No em-dash (`—`)** anywhere in user-facing copy - use `-` or a comma.
- **Gender-neutral Hebrew** - the audience's gender is unknown; avoid gendered verbs
  ("רוצים לחסוך?" not "רוצה לחסוך?" when addressing the public).
- Hebrew first, terse, one idea per line - match the voice of the published posts in
  `docs/marketing/b2c-launch/03-social-posts.md`.

## 3. Tagged links - attribution that actually pays

The consumer page is `https://esim.mocaintel.com/` (mirrors `/esim-deals` on the apex).
Social attribution is **`utm_source` + `utm_campaign`** - `src=esim` is NOT a social
tag and earns nothing in analytics.

| Network | Link pattern |
|---|---|
| Facebook | `https://esim.mocaintel.com/?dest=<slug>&utm_source=facebook&utm_campaign=<campaign>` - goes in the **first comment**, not the post body |
| Instagram | same with `utm_source=instagram` - bio link or story sticker |
| TikTok | same with `utm_source=tiktok&utm_campaign=<campaign>` |

`?lang=he` is optional (Hebrew is default). `dest=` deep-links the destination picker -
use the same Hebrew destination the post talks about. Verify the final URL loads with
the params intact before handing it over.

## 4. Video rules (TikTok/Reels)

- Keep **all** text - captions, CTA, and the end-card URL - inside the **center safe
  zone**. The TikTok GUI covers the edges and bottom; a URL near the bottom gets run
  over (happened on v1, 2026-07-06).
- End-card URL: render smaller and centered, not full-width at the bottom.
- Overlay text sources live in `docs/marketing/b2c-launch/tiktok-veo/README-he.md`.

## 5. Suggest the posting window (always, proactively)

When the user says he's uploading, don't just hand back the copy - recommend a
concrete day+time (Israel audience, 2026 data):

- **Instagram**: Tue-Thu evenings, 20:00-22:00
- **TikTok**: weekends
- **Facebook**: Tue-Thu midday; page convention `post_time` is 20:30
- Israel hero window overall: Sun-Thu 20:00-22:00, plus Motzaei Shabbat

## 6. Facebook pipeline - keep the calendar in sync

Facebook posts are driven by `docs/marketing/b2c-launch/fb-content-calendar.json`
(the source of truth; `scripts/fb_post_reminder.py` reads it daily, pings Telegram
when a pending post is due, re-lints BiDi, and warns when the pending backlog drops
to `meta.pipeline_low_threshold`).

When creating or scheduling an FB post, add/update its entry - fields:
`id, date, time, status (pending|published), title, image (filename under
meta.image_dir = C:\Users\Alon\Desktop\MOCA-Posts), campaign, dest, link, body`.
After publishing, flip `status` to `published`. When the low-backlog warning fires,
generate the next 2 weeks of posts (new destinations + copy + tagged links + images).

## 7. Asset locations

- `Instagram/` - carousel slides + `carousel.html` (rendered to PNGs via Playwright)
  + `MOCA-instagram-content.md` (copy)
- `docs/marketing/b2c-launch/` - launch plan, viral scripts, carousels, storyboards,
  Gary Vee playbook, `tiktok-veo/` video pipeline

## Final gate before handing content back

1. BiDi lint passes (section 1)
2. No em-dash, gender-neutral (section 2)
3. Link tagged with utm_source/utm_campaign and verified (section 3)
4. Video text in center safe zone (section 4)
5. Posting window suggested (section 5)
6. FB calendar updated if relevant (section 6)
