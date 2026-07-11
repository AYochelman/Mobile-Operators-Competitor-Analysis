# MOCA Video Creatives - Batch 2 (2026-07-10)

Top 3 NEW ideas (from the 10-idea research set) turned into Veo-ready storyboards.
Same specs as batch 1: portrait 9:16, ~20s each, NO dialogue / NO on-screen text (Alon adds Hebrew captions later). Photorealistic/cinematic commercial style. 2-3 Veo clips per video, joined with ffmpeg concat.

Generate via Gemini web app Videos gallery (sets Portrait 9:16), 2 clips at a time, download via UI icon, move to this folder.

---

## Video 4 - "I compared them all" (MOCA's exclusive angle)
A chaotic wall of 20+ eSIM provider logos collapses into a single MOCA screen that sorts by price and crowns one winner. This is the angle NO single eSIM seller can claim.

| Clip | Shot | Veo Prompt |
|---|---|---|
| 4a | Chaos | Dozens of colorful app-icon-style logo cards floating and swirling chaotically in a clean white studio space, overwhelming cluttered arrangement, a single sleek smartphone sits calmly in the center foreground, soft studio lighting, shallow depth of field, high-end tech commercial style, photorealistic, 4k, no text, no logos, no readable brand names |
| 4b | Sort + winner | The swirling cluster of cards flies and snaps into a neat vertical sorted list on the smartphone screen, the cards rearrange from messy to a clean ranked column, one card at the top glows with a soft green highlight and gently rises above the others, camera pushes in on the winning card, satisfying organized motion, photorealistic commercial style, cinematic lighting, 4k, no text, no logos |

## Video 5 - "Roaming vs eSIM" (split-screen comparison)
Same trip, two split screens. Left: the roaming traveler sweating as a meter climbs. Right: the eSIM traveler browsing calm. The gap sells itself, no words needed.

| Clip | Shot | Veo Prompt |
|---|---|---|
| 5a | Setup split | Vertical split screen composition, two travelers in identical cafe settings abroad, left side a stressed man staring anxiously at his phone with a worried expression, right side a relaxed woman smiling and scrolling her phone casually sipping coffee, clean cinematic lighting, photorealistic, shallow depth of field, no text, clear vertical dividing line down the middle |
| 5b | Escalation | Vertical split screen, left side the stressed traveler's expression tightens as he clutches his phone tensely and rubs his forehead in growing worry, right side the relaxed traveler laughs and takes a photo of her coffee enjoying herself, warm cinematic tone, photorealistic, shallow depth of field, no text, clear vertical dividing line |
| 5c | Payoff | The vertical dividing line wipes away and both travelers merge into one bright clean frame where the relaxed happy traveler walks confidently through a sunny foreign street holding her phone, warm golden cinematic light, uplifting energy, photorealistic commercial style, no text |

## Video 6 - "How much you saved" (receipt reveal)
A long printed receipt of a roaming bill; the number gets slashed and a big savings figure remains. Numeric proof = the payoff that drives shares.

| Clip | Shot | Veo Prompt |
|---|---|---|
| 6a | The bill | Close-up on a long printed paper receipt unrolling on a wooden table, resembling an expensive mobile roaming bill with many line items, dramatic side lighting, a hand holds the top of the receipt, cinematic macro shot, photorealistic, shallow depth of field, no readable text, no numbers, no logos |
| 6b | The cut | The long receipt is sharply cut and most of it falls away leaving only a small short slip, a smartphone lies beside it on the table with a glowing clean screen, a burst of soft green light pulses over the remaining small slip suggesting big savings, satisfying resolution, cinematic lighting, photorealistic commercial style, 4k, no text, no numbers, no logos |

## Status
- [ ] 4a
- [ ] 4b
- [ ] 5a
- [ ] 5b
- [ ] 5c
- [ ] 6a
- [ ] 6b
- [ ] concat v4_final (4a+4b), v5_final (5a+5b+5c), v6_final (6a+6b)
- [ ] watermark each final: `./apply_watermark.sh v4_final.mp4` etc -> v*_final_wm.mp4 (the deliverable)

## Caption / hook notes for later (Hebrew overlays, added in edit)
- V4: hook "בדקתי את כל ספקי ה-eSIM בשבילך" / CTA "מצא הזול ביותר - esim.mocaintel.com"
- V5: hook "אותה נסיעה. שני מחירים." / CTA "תפסיק לשלם על נדידה"
- V6: hook "כמה באמת אפשר לחסוך?" / payoff "חסכת מאות שקלים" / CTA link
- Keep all text in center safe zone (avoid bottom 15%, right 12%).
