# Supplied-video validation

## Source

- URL: `https://ok.ru/video/248244667877`
- Title reported by the extractor: *The Adventures of Sherlock Holmes: A Scandal
  in Bohemia [Jeremy Brett]*
- Reported duration: 3,261 seconds

## Environment note

The host intermittently dropped TLS connections and throttled its `sd` stream.
The implementation’s bounded retries recovered extraction. For the development
validation only, the lower stream’s progressive opening prefix was retained so
the target occurrence could be processed without waiting for the remaining
episode. The normal URL command downloads and searches the complete selected
stream; the algorithm contains no timestamp, title, or target-specific location.

The retained MP4 prefix still exposed valid source metadata and seekable media:

- 480 x 360
- 23.976166 FPS reported by OpenCV
- enough audio/video to pass the target occurrence

## Important observation

A decoded frame around the target contains no visible dialogue or burned-in
subtitle. An OCR-only design therefore cannot solve the supplied case. This real
check drove the speech-first/visible-text-fallback architecture.

## Result

Using `faster-whisper` `base.en`, English, CPU `int8`:

```text
Status    : found
Timestamp : 00:05:24.840
Frame     : 7788 (0-based)
Text      : "My mind read bells. It's stagnation."
Confidence: 83.486/100
FPS       : 23.97616608930767
```

The ASR mistake is intentionally preserved. Fuzzy similarity recognizes it as
the requested `"My mind rebels at stagnation"`; the system does not rewrite its
evidence to look perfect. The corresponding frame and sanitized JSON are under
`examples/supplied-case/`.

Because Whisper word alignment is probabilistic, this is the frame containing
the model-estimated onset of `My`, not a claim of sample-accurate ground truth.
The next accuracy upgrade is phoneme-level forced alignment with decoder PTS.
