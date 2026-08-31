@echo off
rem Auto-resume TikTok Veo clip generation once Gemini credits are topped up.
rem Runs daily via Task Scheduler (MOCA-TikTok-Veo-Resume). Exits fast (one
rem cheap 429) while credits are depleted; generates whatever is missing once
rem they exist; on full success alerts Telegram and deletes its own task.
cd /d "%~dp0.."
python scripts\gen_tiktok_veo.py >> scripts\gen_tiktok_veo.log 2>&1
if %errorlevel%==0 (
    python scripts\alert.py "TikTok Veo videos ready" "All 10 clips + 5 final videos are ready in docs/marketing/b2c-launch/tiktok-veo (overlay texts in README-he.md)" >> scripts\gen_tiktok_veo.log 2>&1
    schtasks /delete /tn "MOCA-TikTok-Veo-Resume" /f >> scripts\gen_tiktok_veo.log 2>&1
)
