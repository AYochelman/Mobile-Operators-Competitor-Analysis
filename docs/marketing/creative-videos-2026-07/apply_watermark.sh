#!/usr/bin/env bash
# Applies the MOCA watermark (bolt + wordmark) to a video.
# Usage:  ./apply_watermark.sh input.mp4 [output.mp4]
# Default output: <input>_wm.mp4
# Watermark: top-left corner (safest from TikTok/Reels GUI), sized as a % of the
# video width so it looks identical at 720p, 1080p or 4K. 60% opacity.
# White logo with a baked soft shadow so it reads on light AND dark backgrounds.
# Tune the *_FRAC / OPACITY below if needed.

set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WM="$DIR/assets/moca_watermark.png"

IN="${1:?usage: apply_watermark.sh input.mp4 [output.mp4]}"
OUT="${2:-${IN%.*}_wm.mp4}"

WM_FRAC=0.236   # watermark width as fraction of video width (170px on a 720px-wide video)
OPACITY=0.60    # 0..1
MX_FRAC=0.044   # left margin as fraction of video width (32px @ 720)
MY_FRAC=0.061   # top  margin as fraction of video width (44px @ 720)

# Probe the video width so the watermark scales proportionally (robust for 4K).
VW=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$IN" | tr -d '[:space:]')
awkr() { awk "BEGIN{printf \"%d\", ($1)+0.5}"; }
SCALE=$(awkr "$VW*$WM_FRAC")
MX=$(awkr "$VW*$MX_FRAC")
MY=$(awkr "$VW*$MY_FRAC")

ffmpeg -y -i "$IN" -i "$WM" \
  -filter_complex "[1:v]scale=${SCALE}:-1,format=rgba,colorchannelmixer=aa=${OPACITY}[wm];[0:v][wm]overlay=${MX}:${MY}[v]" \
  -map "[v]" -map 0:a? -c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p -c:a copy \
  "$OUT"

echo "watermarked -> $OUT  (video ${VW}px wide, watermark ${SCALE}px)"
