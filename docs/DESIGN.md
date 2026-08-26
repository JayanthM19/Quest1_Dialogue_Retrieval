# Design and approach

## Objective and interpretation

Given a video and target dialogue, return the earliest decoded video frame
associated with that dialogue and the text extracted by the recognition system.

The wording can describe spoken dialogue or visible text. More importantly, the
supplied video contains the target in audio and has no subtitle rendered in the
target frame. The default architecture is therefore hybrid:

1. locate spoken dialogue with ASR word timestamps;
2. if no speech match is found, search visible text with OCR;
3. map the recognized onset to a concrete decoded frame.

## Architecture

The implementation separates these responsibilities:

1. `downloader.py`: local resolution or resilient `yt-dlp` acquisition.
2. `speech.py`: faster-whisper transcription and streaming target matching.
3. `ocr.py`: replaceable offline OCR protocol and RapidOCR adapter.
4. `matcher.py`: visible-text normalization and scoring across OCR line groups.
5. `video.py`: decoding, metadata, frame iteration, regions, and timestamps.
6. `search.py`: coarse-to-fine visible-text temporal localization.
7. `cli.py`: mode selection, artifact writing, and machine-readable exit status.

The OCR protocol and streaming speech matcher are independently testable. Either
recognizer can be replaced without rewriting media acquisition or output logic.

## Determining where to look

No person selects a clip. Speech mode processes audio chronologically from the
beginning. faster-whisper’s voice-activity detector skips silence, and the matcher
examines each new word window as it arrives. The first accepted occurrence stops
transcription, avoiding work after the answer.

OCR mode also starts at the beginning. It samples every two seconds, then uses a
0.5-second pass over unseen frames if the first pass fails. Intervals are converted
using source FPS, so behavior is independent of a particular frame rate.

## Speech extraction and matching

faster-whisper returns word text, start/end time, and probability. For a target of
`N` normalized tokens, the matcher evaluates windows of `N-1`, `N`, and `N+1`
words. Boundary-word checks prevent accepting only a highly similar suffix, which
would incorrectly move the reported onset forward.

Unicode NFKC normalization, case folding, punctuation removal, and fuzzy edit
similarity tolerate recognition mistakes. The combined score is:

```text
fuzzy_similarity * (0.75 + 0.25 * sqrt(mean_ASR_probability))
```

Raw ASR text is returned, not silently replaced with the target. This keeps the
evidence honest and makes fuzzy acceptance explainable.

No runtime LLM prompt or target hint is passed to Whisper. That avoids biasing the
recognizer into hallucinating the requested phrase.

## Visible-text extraction and matching

RapidOCR returns text boxes and confidence. Boxes are clustered into visual rows
before left-to-right sorting, because their top edges often differ slightly.
Consecutive line groups allow a two-line subtitle to match a one-line query.

The OCR combined score is:

```text
fuzzy_similarity * (0.65 + 0.35 * sqrt(mean_OCR_confidence))
```

Full-frame OCR is the general default; `top` and `bottom` regions are performance
options when placement is known.

## Determining the relevant frame

### Spoken dialogue

Let `t` be the first matched word’s ASR start time and `R` the reported FPS. The
selected 0-based constant-rate frame is:

```text
floor(t * R)
```

That is the frame whose display interval contains the estimated audio onset. The
unaltered decoded frame is saved. This is reproducible, although ASR alignment is
an estimate rather than sample-accurate forced alignment.

### Visible dialogue

After a sampled frame matches, the system returns one sampling interval, decodes
sequentially, and OCRs every frame. The first member of two consecutive matching
frames is the visible-text onset. Stability prevents a compression artifact or
single OCR hallucination from becoming the result.

## Ambiguity and uncertainty

Three statuses are possible:

- `found`: the selected recognizer reaches the configured threshold;
- `uncertain`: a score within ten points is retained but does not pass;
- `not_found`: no evidence is strong enough to retain.

The JSON separates fuzzy score, recognizer confidence, combined confidence, raw
extracted text, method, model, and diagnostics. An uncertain CLI run exits nonzero.

Important ambiguity remains in the phrase “exact frame” for speech: sound is
continuous, video is discrete, and ASR alignment is probabilistic. The operational
definition above is explicit. A production upgrade would use phoneme-level forced
alignment plus decoder presentation timestamps and report an onset interval.

## Performance

Speech search is roughly linear in audio duration up to the first match, while the
streaming matcher uses constant memory relative to duration. VAD avoids inference
on silence.

For OCR duration `D`, coarse interval `C`, fallback interval `F`, and frame rate
`R`, OCR work is approximately:

```text
best case:  D/C + C*R
fallback:   D/F + F*R
```

Only individual frames and small recognition windows are retained.

## Deliberate trade-offs

- `base.en` is practical on CPU and small enough for a one-day solution; larger
  models improve difficult audio but increase download and runtime.
- Target text is used only by fuzzy matching, not as a Whisper prompt, reducing
  target-conditioned hallucination risk.
- Offline inference avoids API credentials, rate limits, per-frame costs, and
  media upload/privacy concerns.
- OpenCV is portable and compact but exposes average FPS for VFR material.
- Default `auto` maximizes semantic coverage; explicit modes avoid unnecessary
  model loading when the media type is already known.

## Test strategy

Pure tests verify ASR boundary logic and raw onset preservation. OCR unit tests
cover normalization, noise, and reading order. A deterministic 10 FPS generated
video starts its marker at frame 11; coarse search first observes it at frame 15,
and refinement must return frame 11 (`00:00:01.100`). A real supplied-video run is
recorded in `docs/VALIDATION.md`.
