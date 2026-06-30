# Recording the demo assets

The README has three media slots that turn it from "a repo" into "I want this":

| Slot | File to produce | Used in |
|------|-----------------|---------|
| **Hero demo** (the big one) | `docs/assets/hero.gif` (+ `hero.mp4`) | top of `README.md` |
| **Screenshot gallery** (4 stills) | `docs/assets/shot-canvas.png`, `shot-run.png`, `shot-agent.png`, `shot-kb.png` | `## Screenshots` |
| Logo lockup | `docs/assets/banner.svg` | already done ✅ |

Until real media exists, every slot points at `hero-placeholder.svg` so the page renders
cleanly. You record; the steps below process and wire it in.

---

## 1. The hero clip — exact shot list (~18–25s, looped)

Record one continuous take of **building a workflow from scratch and running it**. Keep it
snappy; trim dead air in post.

1. **(0–2s)** Start on a near-empty canvas — just the `START` node. Let it breathe for a beat.
2. **(2–7s)** Drag an **AGENT** node from the palette onto the canvas. Connect `START → AGENT`.
   Open its config, pick a model, type a short prompt (e.g. *"Summarize the input in one line"*).
3. **(7–12s)** Drag a **CONDITION** node. Connect `AGENT → CONDITION`. Add a tiny CEL
   expression. Drag an **END** node and wire the `true`/`false` branches.
4. **(12–16s)** Click **Run**. Provide a one-line input.
5. **(16–22s)** Show **live execution** — nodes lighting up in order, the debug panel /
   traces streaming, final result. End on the completed run.

**Capture spec**
- Viewport **1280×800** (or 1440×900). Use a clean browser window, no bookmarks bar.
- **Light theme** for the hero (record a dark-theme take too if easy — nice for the docs site).
- Hide anything personal (real API keys, account email, other tabs).
- ~30 fps. Enable cursor highlighting if your recorder supports it.
- Tools: macOS screen recording / [Kap](https://getkap.co) / [ScreenStudio](https://screen.studio) → export **`.mov` or `.mp4`**.

Drop the raw file anywhere and tell me the path — or run the pipeline below yourself.

## 2. The 4 gallery stills

High-res PNG screenshots (same 1280×800 window) of:
- `shot-canvas.png` — a finished, non-trivial workflow on the canvas.
- `shot-run.png` — the execution monitor / debug panel mid- or post-run.
- `shot-agent.png` — an AGENT node's configuration form open.
- `shot-kb.png` — a knowledge base (RAG) screen.

---

## 3. Processing pipeline (run on the raw recording)

Requires `ffmpeg` (and `gifski` for the best-looking GIF: `brew install ffmpeg gifski`).
Run from the repo root with your raw file as `RAW=...`.

```bash
RAW=raw-demo.mov          # your recording
W=840                     # README hero render width

# --- trim (optional): keep 00:00–00:22 ---
ffmpeg -y -i "$RAW" -ss 00:00:00 -to 00:00:22 -c copy trimmed.mov

# --- high-quality MP4 (small, crisp; for the docs site) ---
ffmpeg -y -i trimmed.mov -vf "scale=${W}:-2:flags=lanczos" \
  -c:v libx264 -pix_fmt yuv420p -movflags +faststart -an docs/assets/hero.mp4

# --- high-quality looping GIF (renders inline everywhere on GitHub) ---
# Option A — gifski (best quality):
ffmpeg -y -i trimmed.mov -vf "fps=18,scale=${W}:-2:flags=lanczos" frame-%04d.png
gifski --fps 18 --width $W -o docs/assets/hero.gif frame-*.png && rm frame-*.png

# Option B — pure ffmpeg palette (no extra deps):
ffmpeg -y -i trimmed.mov -vf "fps=18,scale=${W}:-2:flags=lanczos,palettegen" palette.png
ffmpeg -y -i trimmed.mov -i palette.png \
  -lavfi "fps=18,scale=${W}:-2:flags=lanczos[x];[x][1:v]paletteuse" docs/assets/hero.gif
rm -f palette.png trimmed.mov

# --- verify: dimensions, duration, size (keep the GIF under ~8 MB) ---
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,duration \
  -of default=noprint_wrappers=1 docs/assets/hero.gif
ls -lh docs/assets/hero.gif docs/assets/hero.mp4
```

Optimize stills (optional): `pngquant --quality=70-90 --ext .png --force docs/assets/shot-*.png`.

If the GIF is over ~8 MB, drop `fps` to 14–15 or `W` to 760, or shorten the trim window.

## 4. Wire it into the README

Once the files exist, swap the placeholder references:

```bash
cd "$(git rev-parse --show-toplevel)"
# hero slot
sed -i '' 's#docs/assets/hero-placeholder.svg" alt="Assemblix — building#docs/assets/hero.gif" alt="Assemblix — building#' README.md
# gallery slots → point each <img> at its real shot-*.png by hand (4 lines under "## Screenshots")
```

Then commit: `git add docs/assets README.md && git commit -m "docs: add demo GIF and screenshots"`.
