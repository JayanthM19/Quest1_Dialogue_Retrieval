# Dialogue Frame Finder

Find the first video frame associated with a requested dialogue.

The application accepts either a public video URL or a local video file and searches for the requested dialogue using two complementary approaches:

- **Speech search** — `faster-whisper` detects spoken dialogue and provides word-level timestamps.
- **Visible-text search** — RapidOCR searches video frames for burned-in subtitles, captions, or title-card text.

The default `auto` mode uses speech recognition first and falls back to OCR when no suitable speech match is found.

The system returns the earliest frame supported by the selected recognition method, together with the recognized text, timestamp, confidence information, and diagnostic details.

---

## Features

- Public HTTP(S) video URL support through `yt-dlp`
- Local video file support
- Offline speech recognition using `faster-whisper`
- Offline OCR using RapidOCR
- Fuzzy matching to tolerate normal ASR/OCR recognition errors
- Word-level speech timestamps
- Coarse-to-fine OCR temporal search
- Stable-frame verification for visible-text matches
- `FOUND`, `UNCERTAIN`, and `NOT_FOUND` result states
- JSON result output
- Matching-frame image output
- Configurable recognition threshold
- CPU and CUDA execution options
- No API keys required

---

## 1. Requirements

The project requires:

- Python **3.10 or newer**
- Git

System-level FFmpeg and Tesseract installations are not required.

The required media, speech, OCR, and image-processing dependencies are installed through the Python project configuration.

---

## 2. Clone the Repository

Clone the repository:

```bash
git clone https://github.com/JayanthM19/Quest1_Dialogue_Retrieval.git
```

Enter the project directory:

```bash
cd Dialogue_Retrieval
```

If your cloned directory has a different name, use that directory name instead.

---

## 3. Create a Virtual Environment

A virtual environment is recommended so that the project's dependencies remain isolated from other Python projects.

### Windows PowerShell

Create the environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

You should see `(.venv)` at the beginning of your terminal prompt.

### macOS / Linux

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

---

## 4. Install the Project

With the virtual environment activated:

```bash
python -m pip install --upgrade pip
```

Then install the project:

```bash
python -m pip install -e ".[dev]"
```

This installs the application's runtime dependencies and the development/test dependency (`pytest`).

---

## 5. Verify the Installation

Run:

```bash
python -m framefinder --help
```

You should see the command usage and available options.

The two required positional arguments are:

```text
source
dialogue
```

The source can be:

- a public video URL
- a local video file

The dialogue is the text that should be located.

---

## 6. Basic Usage

The general command is:

```bash
python -m framefinder "<VIDEO_SOURCE>" "<TARGET_DIALOGUE>" --output-dir output
```

For example:

```bash
python -m framefinder "https://example.com/video" "My mind rebels at stagnation" --output-dir output
```

The video URL/path and target dialogue are provided through the terminal. They are not hardcoded into the application.

---

## 7. Tested Examples

The following commands were tested against actual videos during development.

### Example 1 — OK.ru

**Video:**

```text
https://ok.ru/video/248244667877
```

**Target dialogue:**

```text
My mind rebels at stagnation
```

Run:

```bash
python -m framefinder "https://ok.ru/video/248244667877" "My mind rebels at stagnation" --output-dir output
```

### Validated result

```text
Status      : found
Timestamp   : 00:05:24.840
Frame       : 7788
Text        : "My mind read bells. It's stagnation."
Confidence  : 83.486/100
FPS         : 23.97616608930767
```

The imperfect ASR transcription is intentionally preserved rather than replaced with the requested text. Fuzzy matching recognizes the transcription as sufficiently similar to the requested dialogue.

### Example 2 — YouTube

**Video:**

```text
https://youtu.be/8LvR63eGYnA
```

**Target dialogue:**

```text
signal from space
```

Run:

```bash
python -m framefinder "https://youtu.be/8LvR63eGYnA" "signal from space" --output-dir output
```
.

---

## 8. Search Modes

The application supports three modes.

### `auto` — default

```bash
--mode auto
```

Uses speech recognition first and OCR as a fallback:

```text
Speech search
     |
     | no adequate match
     v
OCR search
```

This is the recommended mode when it is unknown whether the requested dialogue is spoken or visibly rendered.

### `speech`

```bash
--mode speech
```

Searches the audio using `faster-whisper`.

Use this when the target is expected to be spoken.

### `ocr`

```bash
--mode ocr
```

Searches video frames using RapidOCR.

Use this for burned-in subtitles, captions, title cards, or other visible text.

---

## 9. Useful Options

### Recognition threshold

```bash
--threshold 80
```

Controls the combined fuzzy-recognition threshold from 0 to 100.

Default:

```text
80
```

### ASR model

```bash
--asr-model base.en
```

The default model is:

```text
base.en
```

A larger model can be selected when additional accuracy is more important than processing time:

```bash
--asr-model small
```

### Language

English:

```bash
--language en
```

Automatic language detection:

```bash
--language auto
```

### Device

CPU:

```bash
--device cpu
```

CUDA:

```bash
--device cuda
```

### ASR compute type

```bash
--compute-type int8
```

The appropriate compute type depends on the available hardware.

### OCR sampling

Initial OCR sampling interval:

```bash
--coarse-interval 2.0
```

Fallback sampling interval:

```bash
--fallback-interval 0.5
```

Disable fallback sampling:

```bash
--fallback-interval 0
```

### OCR stability

```bash
--stable-frames 2
```

Requires consecutive matching frames during exact OCR refinement.

### OCR region

Search the complete frame:

```bash
--region full
```

Search the bottom region:

```bash
--region bottom
```

Search the top region:

```bash
--region top
```

For subtitles known to appear at the bottom, `bottom` can reduce unnecessary OCR processing.

### OCR image width

```bash
--max-ocr-width 1280
```

Limits the width of images sent to OCR for faster processing.

### yt-dlp format

A specific media format can be selected with:

```bash
--format <FORMAT>
```

For example:

```bash
--format sd
```

### Certificate verification

Certificate verification is enabled by default.

If a trusted URL cannot be downloaded because of a broken local certificate chain, it can be disabled with:

```bash
--no-check-certificates
```

Use this only when necessary.

---

## 10. Output

The default output directory is:

```text
./output
```

It can be changed with:

```bash
--output-dir <DIRECTORY>
```

For example:

```bash
--output-dir results
```

The application produces machine-readable result information and matching-frame artifacts.

A successful result contains information such as:

- status
- timestamp
- frame number
- extracted text
- confidence

When a match passes the configured threshold, the corresponding frame is saved as an image.

When useful evidence exists but does not meet the final threshold, the application can preserve the candidate frame while reporting an uncertain result.

Generated downloads, temporary files, and output artifacts are excluded from Git through `.gitignore`.

---

## 11. How the System Works

The default `auto` mode follows this flow:


```text
                         ┌──────────────────────────┐
                         │     User / Evaluator      │
                         └────────────┬─────────────┘
                                      │
                                      │
                         Video URL + Target Dialogue
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │        CLI Layer         │
                         │                          │
                         │  - Parse video source    │
                         │  - Parse target text     │
                         │  - Parse configuration   │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │    Search Controller     │
                         │                          │
                         │ Coordinates the selected │
                         │ search mode and stages   │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │     Media Acquisition    │
                         │                          │
                         │ yt-dlp / local media     │
                         │ FFmpeg-based processing  │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                         ▼                         ▼
                ┌──────────────────┐      ┌──────────────────┐
                │   Audio Search   │      │   Visual Search  │
                │                  │      │                  │
                │ faster-whisper   │      │ Frame sampling   │
                │ transcription    │      │ + RapidOCR       │
                │                  │      │                  │
                │ Timestamped      │      │ OCR text +       │
                │ speech segments  │      │ confidence       │
                └────────┬─────────┘      └────────┬─────────┘
                         │                         │
                         ▼                         ▼
                ┌──────────────────┐      ┌──────────────────┐
                │ Speech Matching  │      │  OCR Matching    │
                │                  │      │                  │
                │ Target dialogue  │      │ Normalize text   │
                │ vs ASR output    │      │ + fuzzy matching │
                └────────┬─────────┘      └────────┬─────────┘
                         │                         │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │    Candidate / Time      │
                         │        Selection         │
                         │                          │
                         │ Identify promising      │
                         │ temporal region(s)       │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │   Frame Localization     │
                         │                          │
                         │ Coarse-to-fine temporal  │
                         │ search and verification  │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │     Result Generation    │
                         │                          │
                         │ Matching timestamp       │
                         │ Matching frame           │
                         │ Recognition information  │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │      Output Directory    │
                         │                          │
                         │ Saved result artifacts    │
                         └──────────────────────────┘
```

### Speech Search

`faster-whisper` processes the audio chronologically and provides:

- recognized words
- word start/end timestamps
- recognition probabilities

The target dialogue is normalized and compared against sliding word windows using fuzzy similarity.

The target itself is not passed to Whisper as a prompt. It is used only by the matching layer.

Once a sufficiently strong match is found, transcription can stop because the earliest acceptable occurrence has already been identified.

### OCR Search

When speech does not provide an adequate result, OCR searches the video chronologically.

The search uses:

- coarse frame sampling
- a denser fallback search when necessary
- sequential frame refinement around a promising match
- stable consecutive-frame verification

The first frame satisfying the configured matching and stability requirements is selected.

---

## 12. Matching and Confidence

The system does not require exact string equality.

Recognition errors such as:

```text
rebels
```

being recognized as:

```text
rebles
```

can still be accepted when the overall evidence is sufficiently similar.

### Speech confidence

The speech matching score combines fuzzy text similarity with the mean ASR probability:

```text
fuzzy_similarity *
(0.75 + 0.25 * sqrt(mean_ASR_probability))
```

### OCR confidence

The OCR score combines fuzzy text similarity with the mean OCR confidence:

```text
fuzzy_similarity *
(0.65 + 0.35 * sqrt(mean_OCR_confidence))
```

These combined scores are used for the final matching decision rather than relying only on raw recognizer confidence.

---

## 13. Result States

The application distinguishes between three outcomes.

### `found`

The recognition score reaches the configured threshold and sufficient evidence exists to report a result.


### `not_found`

No sufficiently strong evidence was found.

This prevents the application from silently presenting an unreliable frame as an exact answer.

---

## 14. Exact Frame Interpretation

For spoken dialogue, the selected frame corresponds to the model-estimated onset of the first matched word.

For a constant-frame-rate video:

```text
frame = floor(timestamp × FPS)
```

The decoded frame itself is preserved as the output image.

This should not be interpreted as sample-accurate ground truth because speech recognition timestamps are model-derived estimates.

For visible dialogue, the system identifies the first frame in a stable matching sequence during frame-by-frame refinement.

---

## 15. Tests

Run the complete test suite with:

```bash
python -m pytest -v
```

or:

```bash
pytest
```

The tests cover areas including:

- speech matching
- first-word timestamp preservation
- rejection of incorrect phrase suffixes
- Unicode/case/punctuation normalization
- fuzzy OCR matching
- multi-line OCR reading order
- deterministic video-frame refinement
- no-match behavior

Detailed validation information is available in:

```text
docs/VALIDATION.md
```

The detailed architecture and implementation decisions are documented in:

```text
docs/DESIGN.md
```

---

## 16. Exit Codes

The CLI uses the following exit codes:

```text
0 → found
2 → uncertain / not_found
1 → setup, download, transcription, or decoding error
```

This makes the application suitable for both manual execution and automated evaluation.

---

## 17. Limitations

The following limitations should be considered when evaluating the system:

- Speech timestamps are model-derived and are not sample-accurate ground truth.
- Very noisy audio or overlapping speakers can reduce ASR accuracy.
- Very small or highly stylized text can reduce OCR accuracy.
- Uncommon languages may require a different or larger recognition model.
- URL support depends on the upstream site's `yt-dlp` extractor.
- Variable-frame-rate video can make direct timestamp-to-frame mapping approximate.
- Larger ASR models can improve difficult cases at the cost of additional download size and runtime.

These limitations are intentionally exposed rather than hidden behind fabricated precision.

---

## 18. Repository Structure

```text
Dialogue_Retrieval/
│
├── src/
│   └── framefinder/
│       ├── cli.py
│       ├── downloader.py
│       ├── matcher.py
│       ├── ocr.py
│       ├── search.py
│       ├── speech.py
│       └── video.py
│
├── tests/
│
├── docs/
│   ├── DESIGN.md
│   └── VALIDATION.md
│
├── APPROACH.md
├── prompts.txt
├── README.md
├── pyproject.toml
└── .gitignore
```

---


## Documentation

For the engineering approach:

```text
APPROACH.md
```

For detailed system design:

```text
docs/DESIGN.md
```

For validation results:

```text
docs/VALIDATION.md
```