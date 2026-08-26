# Dialogue Frame Finder

Find the **first video frame** associated with a requested dialogue. The program
accepts a public media URL or local video and supports both meanings of “dialogue
appears”:

- **spoken dialogue**: offline speech recognition supplies word timestamps;
- **visible dialogue**: offline OCR searches burned-in subtitles or title cards.

It produces:

- `result.json` with status, timestamp, 0-based frame number, extracted text,
  recognition method, confidence, and diagnostics;
- `exact-frame.png` when the match passes the configured threshold;
- `candidate-frame.png` when useful evidence remains uncertain.

The URL and target dialogue are CLI inputs; neither is hardcoded.

## Quick start

Python 3.10+ is required. System FFmpeg and Tesseract are not required. PyAV and
OpenCV supply bundled media decoding; faster-whisper and RapidOCR run locally.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Run the supplied case:

```powershell
find-dialogue-frame `
  "https://ok.ru/video/248244667877" `
  "My mind rebels at stagnation" `
  --output-dir output
```

Local files use the same command:

```bash
find-dialogue-frame ./movie.mp4 "My mind rebels at stagnation"
```

On its first speech run, the program downloads the selected faster-whisper model
to `<output-dir>/models`. The default `base.en` model balances English accuracy,
CPU speed, and one-day-project size. Use `--language auto --asr-model small` for
multilingual material when additional runtime/download size is acceptable.

The command exits `0` for `found`, `2` for `uncertain`/`not_found`, and `1` for
setup, download, transcription, or decoding errors.

## How it works

### Default: automatic hybrid search

1. **Acquire**: use a local file, or let `yt-dlp` download a video-only stream.
   Bounded retries handle unstable media hosts.
2. **Transcribe chronologically**: faster-whisper emits individual words with
   start/end times and probabilities. The pipeline stops at the first strong
   target match; it does not need a manually chosen clip.
3. **Target-directed matching**: normalize Unicode, casing, punctuation, and
   whitespace; then score sliding ASR-word windows with fuzzy edit similarity
   moderated by ASR confidence. This tolerates errors such as “read bells” for
   “rebels” without replacing the extracted text with the requested text.
4. **Map time to frame**: map the first matched word time to the 0-based frame
   whose display interval contains that audio onset and save the original frame.
5. **OCR fallback**: if speech finds no adequate match in `auto` mode, RapidOCR
   samples frames chronologically. A coarse pass, denser fallback, and per-frame
   local refinement find the first stable visible-text match.
6. **Uncertainty**: near matches are returned as `uncertain`; weak evidence is
   `not_found`. The application never silently fabricates an exact result.

The supplied OK.ru video has spoken dialogue but no burned-in text at the target,
which is why speech is the primary strategy. See [docs/DESIGN.md](docs/DESIGN.md)
for design details and [docs/VALIDATION.md](docs/VALIDATION.md) for the real run.

## Useful options

```text
--mode auto|speech|ocr    Speech then OCR, speech only, or visible-text OCR only
--threshold 80           Combined recognition/fuzzy threshold from 0-100
--asr-model base.en      faster-whisper model name or local model directory
--language en            Language code; use auto for detection
--device cpu             Use cuda on a configured NVIDIA environment
--compute-type int8      ASR numerical mode (hardware dependent)
--coarse-interval 2.0    Initial OCR sampling interval in seconds
--fallback-interval 0.5  Denser OCR retry interval; 0 disables it
--stable-frames 2        Consecutive OCR matches required during refinement
--region full            OCR full, bottom, or top of each frame
--max-ocr-width 1280     Downscale wide OCR images for speed
--format FORMAT          yt-dlp format selector for URL sources
--no-check-certificates  Opt-in workaround for a broken local TLS chain
```

For visible subtitles, `--mode ocr --region bottom` is faster and reduces noise.
Keep `full` when text placement is unknown.

If a site exposes named formats, a smaller stream can accelerate processing
without changing timing. The supplied OK.ru page exposes an `sd` format:

```powershell
find-dialogue-frame $url $dialogue --format sd
```

Certificate checking remains enabled by default. Use
`--no-check-certificates` only for a trusted URL when the local certificate store
is known to be broken.

## Tests

```bash
pytest
```

Tests cover:

- streaming speech matching and preservation of the first-word timestamp;
- rejection of a phrase suffix that would shift the onset forward;
- Unicode/case/punctuation normalization and fuzzy OCR matching;
- multi-line OCR reading order;
- a generated video whose later coarse hit must refine to frame 11;
- explicit no-match behavior.

## Exactness and limitations

- For spoken dialogue, “first” means the frame containing the speech model’s
  estimated first-word onset. Word alignment is model-derived evidence, not a
  sample-accurate ground truth; the JSON exposes raw text and confidence.
- For visible dialogue, “first” means the first frame in a stable run whose OCR
  evidence reaches threshold.
- Frame numbering is 0-based. Constant-frame-rate timestamp mapping is direct.
  OpenCV exposes average FPS for variable-frame-rate files, so timestamps there
  are approximate; decoder presentation timestamps are the production upgrade.
- Very noisy audio, overlapping speakers, stylized text, extremely small text,
  or uncommon languages can require a larger ASR/OCR model.
- URL support depends on the upstream site and `yt-dlp` extractor. A downloaded
  local file is always accepted as a fallback source.
- Each `<output-dir>/downloads` folder is a single-video cache. After a new URL
  downloads successfully, FrameFinder removes the previous generated video from
  that folder. Use separate output directories only when you want to retain
  downloads from separate runs.
