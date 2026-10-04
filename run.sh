#!/usr/bin/env bash
# Talking-head video pipeline (runs in the Higgsfield sandbox or any Linux box with ffmpeg + python3).
#
#   bash run.sh transcribe <video_url_or_path> <workdir>   # step 1: download + word-level transcript
#   bash run.sh render <workdir> [all|reel|youtube]        # step 2: plan + render + sound + mux (+ upload)
#
# <workdir>/job.json holds the per-video settings (see jobs/example-ai-notetakers.json).
# Optional keys used only at run time (never commit them): "reel_upload", "youtube_upload" —
# presigned PUT URLs; finished files are uploaded there when present.
# Long renders: launch with  HYPERFRAMES_RENDER_DETACHED=1 setsid nohup bash run.sh render ... &
# and watch <workdir>/status.log.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; P="$REPO/pipeline"
CMD="${1:?usage}"; TOOLS="${TOOLS:-$HOME/.vw-tools}"; mkdir -p "$TOOLS"
export FONT="${FONT:-/usr/share/fonts/truetype/higgsfield/Montserrat-ExtraBold.ttf}"
[ -f "$FONT" ] || export FONT="$(fc-match -f '%{file}' 'Montserrat:weight=800' 2>/dev/null || fc-match -f '%{file}' 'sans:bold')"
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$WD/status.log"; }

audio_index() { ffprobe -v error -select_streams a -show_entries stream=index,codec_name -of csv=p=0 "$1" | awk -F, '$2=="aac"{print $1; exit}'; }

need_node22() {
  if node -e 'process.exit(+process.versions.node.split(".")[0] >= 22 ? 0 : 1)' 2>/dev/null; then N22=node; return; fi
  [ -x "$TOOLS/n22/node_modules/node/bin/node" ] || (mkdir -p "$TOOLS/n22" && cd "$TOOLS/n22" && npm i -s node@22 >/dev/null 2>&1)
  N22="$TOOLS/n22/node_modules/node/bin/node"
}
need_hyperframes() {
  need_node22
  [ -f "$TOOLS/hf/node_modules/hyperframes/bin/hyperframes.mjs" ] || (mkdir -p "$TOOLS/hf" && cd "$TOOLS/hf" && npm i -s hyperframes@0.8.123 >/dev/null 2>&1)
  HF="$N22 $TOOLS/hf/node_modules/hyperframes/bin/hyperframes.mjs"
  export HYPERFRAMES_SKIP_SKILLS=1 HYPERFRAMES_RENDER_DETACHED=1
  $HF browser ensure >/dev/null 2>&1 || true
}
need_py() { python3 -c "import cv2" 2>/dev/null || pip install -q opencv-python-headless >/dev/null 2>&1; }
need_rvm() {
  python3 -c "import torch" 2>/dev/null || pip install -q torch --index-url https://download.pytorch.org/whl/cpu >/dev/null 2>&1
  [ -s "$TOOLS/rvm.ts" ] || curl -sL -o "$TOOLS/rvm.ts" https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.torchscript
}

case "$CMD" in
transcribe)
  SRC_URL="$2"; WD="$3"; mkdir -p "$WD"
  if [ ! -s "$WD/src.mp4" ]; then
    if [ -f "$SRC_URL" ]; then cp "$SRC_URL" "$WD/src.mp4"; else curl -sfL -o "$WD/src.mp4" "$SRC_URL"; fi
  fi
  AI=$(audio_index "$WD/src.mp4"); log "source ok, audio stream $AI"
  ffmpeg -v error -y -i "$WD/src.mp4" -map 0:$AI -ac 1 -ar 16000 "$WD/a.wav"
  PROMPT=$(python3 -c "import json;b=json.load(open('$REPO/brands.json'));print(', '.join(v['name'] for k,v in b.items() if not k.startswith('_'))+'.')")
  python3 "$P/transcribe.py" "$WD/a.wav" "$WD/words.json" "$PROMPT" | tee -a "$WD/status.log"
  [ -f "$WD/job.json" ] || echo '{}' > "$WD/job.json"
  python3 "$P/plan.py" "$WD/words.json" "$WD/job.json" "$WD/timeline.json" | tee -a "$WD/status.log"
  log "TRANSCRIBE DONE"
  ;;
render)
  WD="$2"; WHAT="${3:-all}"; cd "$WD"
  DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 src.mp4)
  python3 - "$DUR" <<'PY'
import json, sys; j = json.load(open('job.json')); j['duration'] = round(float(sys.argv[1]), 3); json.dump(j, open('job.json', 'w'), indent=1)
PY
  python3 "$P/plan.py" words.json job.json timeline.json | tee -a status.log
  mkdir -p logos
  for d in $(python3 -c "import json;print(' '.join(b['domain'] for b in json.load(open('timeline.json'))['brands'].values()))"); do
    [ -s "logos/$d.png" ] || curl -sL -o "logos/$d.png" "https://www.google.com/s2/favicons?domain=$d&sz=256"
  done
  need_py; python3 "$P/icons.py" timeline.json logos | tee -a status.log
  python3 "$P/sfx.py" timeline.json sfx.wav >/dev/null
  AI=$(audio_index src.mp4)
  mux() {  # mux <video> <out>
    ffmpeg -v error -y -i "$1" -i src.mp4 -i sfx.wav -filter_complex \
      "[1:$AI]aresample=48000[v];[2:0]volume=0.8[s];[v][s]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]" \
      -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -movflags +faststart -shortest "$2"
  }
  upload() {  # upload <file> <json-key>
    U=$(python3 -c "import json;print(json.load(open('job.json')).get('$2',''))")
    [ -n "$U" ] && curl -f -s -o /dev/null -w "$2 PUT %{http_code}\n" -X PUT -H "Content-Type: video/mp4" -H "If-None-Match: *" --upload-file "$1" "$U" | tee -a status.log || true
  }
  if [ "$WHAT" = all ] || [ "$WHAT" = reel ]; then
    if [ ! -s alpha.mp4 ]; then log "cutout (RVM)…"; need_rvm; python3 "$P/matte.py" src.mp4 alpha.mp4 "$TOOLS/rvm.ts" >> status.log 2>&1; fi
    log "rendering Reel…"; NW=${NW:-5} python3 "$P/reel.py" timeline.json src.mp4 alpha.mp4 logos reel_video.mp4 >> status.log 2>&1
    mux reel_video.mp4 reel.mp4; log "REEL DONE $(ffprobe -v error -show_entries format=duration -of csv=p=0 reel.mp4)s"; upload reel.mp4 reel_upload
  fi
  if [ "$WHAT" = all ] || [ "$WHAT" = youtube ]; then
    need_hyperframes
    if [ ! -d hfp ]; then $HF init hfp --example blank --resolution landscape --non-interactive --skip-transcribe >/dev/null 2>&1; fi
    if [ ! -s hfp/plate.mp4 ]; then
      log "building 16:9 plate…"
      ffmpeg -v error -y -i src.mp4 -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,split[a][b];[a]scale=1920:-2,crop=1920:1080,boxblur=40:4,eq=brightness=-0.22:saturation=0.75[bg];[b]scale=-2:1080[fg];[bg][fg]overlay=(W-w)/2:0" \
        -an -c:v libx264 -preset veryfast -crf 17 -r 30 -g 30 -keyint_min 30 -pix_fmt yuv420p -color_trc bt709 -movflags +faststart hfp/plate.mp4
    fi
    rm -rf hfp/logos && cp -r logos hfp/logos
    python3 "$P/youtube.py" timeline.json hfp | tee -a status.log
    log "rendering YouTube (HyperFrames)…"
    (cd hfp && rm -rf work-* && $HF render -q looks --sdr --no-low-memory-mode -w ${HFW:-3} -o ../youtube_video.mp4 > ../hf_render.log 2>&1) || { tail -5 hf_render.log | tee -a status.log; exit 1; }
    mux youtube_video.mp4 youtube.mp4; log "YOUTUBE DONE $(ffprobe -v error -show_entries format=duration -of csv=p=0 youtube.mp4)s"; upload youtube.mp4 youtube_upload
  fi
  log "ALL DONE"
  ;;
*) echo "unknown command $CMD"; exit 2;;
esac
