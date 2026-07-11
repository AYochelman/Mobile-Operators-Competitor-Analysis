#!/usr/bin/env bash
# Applies the MOCA watermark (bolt + wordmark) to a video.
# Usage:  ./apply_watermark.sh input.mp4 [output.mp4]
# Default output: <input>_wm.mp4
# Watermark: top-left corner (safest from TikTok/Reels GUI), ~170px wide, 60% opacity.
# White logo with a baked soft shadow so it reads on light AND dark backgrounds.
# Tune SCALE / OPACITY / MX / MY below if needed.

set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WM="$DIR/assets/moca_watermark.png"

IN="${1:?usage: apply_watermark.sh input.mp4 [output.mp4]}"
OUT="${2:-${IN%.*}_wm.mp4}"

SCALE=170      # watermark width in px (height auto)
OPACITY=0.60   # 0..1
MX=32          # left margin px
MY=44          # top margin px

ffmpeg -y -i "$IN" -i "$WM" \
  -filter_complex "[1:v]scale=${SCALE}:-1,format=rgba,colorchannelmixer=aa=${OPACITY}[wm];[0:v][wm]overlay=${MX}:${MY}[v]" \
  -map "[v]" -map 0:a? -c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p -c:a copy \
  "$OUT"

echo "watermarked -> $OUT"
