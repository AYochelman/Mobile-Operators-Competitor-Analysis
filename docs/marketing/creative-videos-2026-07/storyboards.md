# MOCA Video Creatives - 2026-07-10

3 concepts, portrait 9:16, ~20s each, no dialogue/no on-screen text (added later by Alon). Generated via Gemini web app (Veo), 2-3 clips per video joined with ffmpeg. Photorealistic/cinematic commercial style throughout.

## Video 1 - "The eSIM Pill" (product visual)
Giant phone swallows a glowing capsule pill containing the eSIM MOCA picked; screen "digests" it and lights up with full signal.

| Clip | Shot | Veo Prompt |
|---|---|---|
| 1a | Establishing | Giant modern smartphone floating in a minimalist white studio, dramatic soft studio lighting, a glowing translucent blue capsule pill containing a tiny holographic SIM card symbol hovers above the phone screen, slow cinematic push-in, shallow depth of field, high-end tech commercial style, photorealistic, 4k, no text, no logos |
| 1b | Payoff | The glowing pill capsule descends and gets absorbed into the smartphone screen like liquid mercury, ripples spread across the glass surface, a burst of blue light pulses outward, then the phone screen lights up showing full signal bars and a 5G icon, camera pulls back to reveal a clean product shot with soft reflections on a glossy floor, photorealistic commercial style, cinematic lighting, 4k, no text, no logos |

## Video 2 - "Vacation Peace of Mind" (emotional/lifestyle)
Man looks stressed while wife packs for a family trip; he has a lightbulb moment, checks MOCA, then relaxes.

| Clip | Shot | Veo Prompt |
|---|---|---|
| 2a | Setup | Medium shot, cozy modern living room in warm golden afternoon light, a man in his late 30s sits on the couch looking pensive and slightly stressed, rubbing his temple, in the background his wife happily folds clothes into an open suitcase on the bed, beach towels and sunscreen visible nearby, warm cinematic tone, photorealistic, shallow depth of field, no text |
| 2b | Turn | Close-up on the man's face, his worried expression shifts into sudden realization, eyes light up, a soft glowing blue SIM-card-shaped icon appears above his head like a lightbulb moment, warm cinematic lighting, photorealistic close-up, shallow depth of field, no text |
| 2c | Payoff | The man sits up holding his phone, scrolling with a satisfied smile, camera pulls back to a wide shot of the living room where he and his wife now laugh together packing the suitcase side by side, joyful relaxed energy, warm golden light, photorealistic cinematic style, no text |

## Video 3 - "Landing in Japan" (trust/travel)
Businesswoman arrives at a Tokyo hotel unsure how to get connected; the receptionist shows her MOCA on a tablet.

| Clip | Shot | Veo Prompt |
|---|---|---|
| 3a | Establishing | Elegant modern hotel lobby in Tokyo at dusk, shoji-inspired wood screens, city lights glowing through floor-to-ceiling windows, a professional businesswoman in her 30s with a rolling suitcase walks up to the front desk looking slightly puzzled while glancing at her phone, cinematic photorealistic style, no text |
| 3b | Interaction | Medium two-shot at the reception desk, the businesswoman gestures while asking a question, the smiling hotel receptionist nods warmly and turns a sleek tablet screen toward her, soft ambient lobby lighting glowing on the screen, photorealistic cinematic commercial style, no text |
| 3c | Payoff | Close-up on the businesswoman's face as she looks at the tablet screen, her expression shifts to relief and a warm smile, she nods thank you, camera pulls back to a wide elegant shot of her walking confidently toward the elevator with her suitcase, cinematic golden-hour toned lighting, photorealistic, no text |

## Status (2026-07-10)
- [x] 1a
- [x] 1b
- [x] 2a
- [x] 2b
- [ ] 2c - BLOCKED, hit Gemini daily video quota ("Sorry, I can't generate more videos for you today, but come back tomorrow")
- [ ] 3a - blocked same reason (also mis-fired into image mode once by mistake - ignore the "Image Generation Limit Reached" chat, unrelated image quota, not video)
- [ ] 3b
- [ ] 3c
- [x] concat v1_final (done - v1_p1 + v1_p2, 720x1280, ~20s)
- [ ] concat v2_final - needs 2c first
- [ ] concat v3_final - needs 3a/3b/3c first

Resume tomorrow: reuse chat "Preparing for Vacation, One Pensive Moment" for 2c (prompt is clip 2c row above), start a fresh chat via Videos gallery template (sets Portrait 9:16 properly) for 3a/3b/3c in order.

## Watermark (final step for EVERY video)
After concatenating a v*_final.mp4, brand it:
```
./apply_watermark.sh v2_final.mp4      # -> v2_final_wm.mp4
```
Watermark = MOCA bolt + wordmark, white, top-left corner, ~170px wide, 60% opacity (assets/moca_watermark.png). Alon chose 60% over 82% (2026-07-10). The _wm.mp4 is the deliverable. Rationale + evidence: watermark is top-left because TikTok/Reels GUI covers the right (~12%) and bottom (~15%); MOCA's name IS the destination URL so persistent branding directly supports conversion. Regenerate the PNG only if the logo changes (built via canvas Path2D from BOLT_PATH in Logo.jsx).
- [x] v1_final_wm.mp4 done (delivered)
