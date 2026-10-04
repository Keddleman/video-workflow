# video-workflow

One recording in, two edits out:

- **Reel (9:16)** — the original background is kept, and the speaker is cut out so brand logos rise from behind the head the moment each product is named. Word-by-word captions, headline banners, and a "COMMENT <KEYWORD>" card that slams in with a screen shake.
- **YouTube (16:9)** — the speaker full-height in the centre, with a blurred copy of the real room on both sides. Logos pop into the side panels, with headlines on the left and the same captions and CTA. Built with [HyperFrames](https://github.com/heygen-com/hyperframes).

Sound effects (a whoosh and pop per logo, a bass hit per CTA) are generated in code and mixed under the original voice. Everything here is open source and runs on CPU.

## Use

```bash
bash run.sh transcribe <video_url_or_path> work/my-video   # download + word-level transcript + first plan
# edit work/my-video/job.json (keyword, headlines, chips...) — see jobs/example-ai-notetakers.json
HYPERFRAMES_RENDER_DETACHED=1 setsid nohup bash run.sh render work/my-video all > /dev/null 2>&1 &
tail -f work/my-video/status.log                          # → reel.mp4, youtube.mp4
```

## What's automatic

`pipeline/plan.py` reads the transcript and works out the edit:

- **Logo pops:** finds every product in `brands.json` that you name. Mentions within 4 s of each other form one group, shown as a row of up to 5, a pair, or a single logo. Saying a product again while its logo is on screen makes the logo pulse instead of repeating.
- **CTA slams:** finds each time you say "comment <keyword>". The last one holds to the end.
- **Zooms:** adds small punch-ins at the key moments.

## What `job.json` adds

| key | what |
|---|---|
| `keyword`, `cta_line` | CTA card text (`COMMENT / FILTER / GET THE FREE SKILL`) |
| `chips` | label pill joined to a logo pair, e.g. `{"text":"MCP","when":"mcp"}` (`when` = a phrase from the transcript) |
| `banners` | headline per section: `t_in`, `t_out`, `label`, `color`, `text` |
| `cards` | "summary cards pile up, then collapse into one result card" effect |
| `steps` | numbered end-steps on the YouTube layout |
| `extra_mentions`, `ignore_brands` | manual fixes for the auto logo detection |

To add a brand, add it to `brands.json`. The logo is fetched from the brand's site icon at render time, so no logos are stored here.

## Layout

```
run.sh               entry point (transcribe | render)
brands.json          product registry used for logo detection
pipeline/plan.py     transcript + job → timeline.json
pipeline/reel.py     9:16 compositor (Python/OpenCV/Pillow)
pipeline/matte.py    speaker cutout (Robust Video Matting, CPU)
pipeline/youtube.py  16:9 HyperFrames composition (+ youtube.css)
pipeline/sfx.py      synthesised sound effects
pipeline/transcribe.py  faster-whisper word timestamps
jobs/                example job files (no media links)
```

## Notes

- Requires ffmpeg, python3 (numpy, Pillow, faster-whisper), and Node ≥ 22 for HyperFrames. `run.sh` installs Node 22, HyperFrames, OpenCV, torch-cpu and the matting weights on first use.
- iPhone HDR (HLG) footage is rendered as SDR (`--sdr`). Without that flag, HyperFrames tries to render in HDR and runs out of disk space.
- HyperFrames cancels a render when the process that launched it exits. In sandboxes where that process goes away, set `HYPERFRAMES_RENDER_DETACHED=1`.
- About 1 GB of RAM per Reel worker; `NW=5` fits in 8 GB.
