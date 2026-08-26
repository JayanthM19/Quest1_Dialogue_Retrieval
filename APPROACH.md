# Approach

## 1. Problem Understanding

The objective is to locate the earliest video frame associated with a requested dialogue and return:

- the timestamp;
- the frame number;
- the extracted dialogue text;
- the corresponding video frame as an image.

The input is a video URL or local video file together with a target dialogue.

The system must work without requiring manual inspection of the video and should tolerate normal differences in video quality, resolution, frame rate, and text appearance.

The most important distinction in the problem is between:

1. **spoken dialogue**, which can be located using speech recognition; and
2. **visible dialogue**, such as subtitles or title-card text, which can be located using OCR.

Because the target may be available through either source, the implementation uses a hybrid recognition strategy.

---

# 2. Overall Approach

The implemented system follows this general flow:

```text
                    Video + Target Dialogue
                              |
                              v
                     CLI / Search Setup
                              |
                              v
                     Media Acquisition
                              |
                  +-----------+-----------+
                  |                       |
                  v                       v
             Speech Search           OCR Search
          faster-whisper             RapidOCR
                  |                       |
                  v                       v
          Timestamped words        Sampled video frames
                  |                       |
                  v                       v
          Target text matching      OCR text matching
                  |                       |
                  +-----------+-----------+
                              |
                              v
                    Frame Localization
                              |
                              v
                         Final Result
                              |
                              v
                     Output Artifacts
```

The default `auto` mode uses the speech path first. If an adequate speech match cannot be found, the system falls back to visual OCR.

This design is intentional because speech recognition can provide a very efficient temporal index for spoken dialogue, while OCR provides an independent mechanism for dialogue that is visibly rendered in the video.

---

# 3. Why Speech Recognition Is Used

Searching a long video frame-by-frame with OCR would be unnecessarily expensive.

For example, a one-hour video at 30 FPS contains approximately:

```text
60 × 60 × 30 = 108,000 frames
```

Running a relatively expensive OCR model against all of them would be wasteful.

If the requested dialogue is spoken, the audio track provides a much cheaper temporal signal.

The implemented system therefore uses `faster-whisper` to process the audio chronologically and identify where the target dialogue is spoken.

Conceptually:

```text
Audio
  |
  v
faster-whisper
  |
  v
Timestamped words
  |
  v
Target dialogue matching
  |
  v
Approximate occurrence time
```

The speech recognizer provides:

- recognized words;
- start and end timestamps;
- recognition probabilities.

The matcher then determines whether a sequence of recognized words corresponds sufficiently closely to the requested dialogue.

---

# 4. Speech Matching

The system does not require the ASR output to exactly equal the requested dialogue.

Speech recognition can introduce errors such as:

```text
Target:
My mind rebels at stagnation

ASR:
My mind read bells at stagnation
```

or other phonetic/recognition variations.

To handle this, the implementation normalizes the text and uses fuzzy similarity.

The normalization process includes:

- Unicode NFKC normalization;
- case folding;
- punctuation removal;
- whitespace normalization.

The speech matcher evaluates sliding windows around the target length.

For a target containing `N` normalized tokens, the implementation considers windows of:

```text
N - 1
N
N + 1
```

words.

This provides some tolerance for missing or additional recognized words.

Boundary-word checks are also used so that a highly similar suffix or prefix does not incorrectly become the reported occurrence.

---

# 5. Speech Confidence

The system does not rely solely on fuzzy string similarity.

The ASR output also contains recognition probabilities.

The speech score combines:

```text
fuzzy text similarity
+
mean ASR probability
```

The implemented combined score is:

```text
fuzzy_similarity *
(0.75 + 0.25 * sqrt(mean_ASR_probability))
```

This means that a strong textual match is preferred, while ASR confidence also contributes to the final decision.

The raw recognized text is preserved rather than silently replacing it with the requested dialogue.

This is important because the output should represent what the recognition system actually observed.

---

# 6. Mapping Speech Time to a Video Frame

Once the target is found in the speech transcript, the first matched word provides an estimated onset time.

Let:

```text
t = start time of the first matched word
R = reported video frame rate
```

For constant-frame-rate video, the implementation maps the timestamp to a 0-based frame using:

```text
frame = floor(t × R)
```

The selected frame is the frame whose display interval contains the estimated speech onset.

The original decoded frame is then used for the output rather than an OCR-preprocessed image.

An important limitation is that ASR timestamps are model-derived estimates. They are not sample-accurate forced-alignment ground truth.

---

# 7. Why OCR Is Still Necessary

Speech recognition cannot solve every interpretation of "dialogue appears."

The requested text may be:

- visible subtitles;
- a title card;
- text in a silent scene;
- an on-screen quote;
- other rendered text.

The text may therefore exist visually without occurring in the audio.

For that reason, the system contains an independent OCR path.

The architecture is:

```text
Video
  |
  v
Frame sampling
  |
  v
RapidOCR
  |
  v
Recognized text + confidence
  |
  v
Target matching
  |
  v
Temporal localization
```

This also means that a failure to find the target in speech does not automatically mean that the dialogue does not exist in the video.

---

# 8. OCR Processing

RapidOCR is used as the local OCR engine.

The OCR component receives video frames and returns recognized text regions together with confidence information.

The OCR output contains information such as:

```text
text
bounding box
confidence
```

The text boxes are not simply concatenated in arbitrary detector order.

Instead, boxes are clustered into visual rows and sorted from left to right.

This matters because the detector may return text boxes whose vertical coordinates differ slightly even when they belong to the same subtitle line.

The implementation therefore attempts to reconstruct the visual reading order before matching the OCR text against the target.

---

# 9. Multi-Line OCR Matching

A subtitle may occupy more than one visual line.

For example:

```text
My mind rebels
at stagnation
```

while the target is supplied as:

```text
My mind rebels at stagnation
```

The OCR matcher therefore supports consecutive line groups so that a multi-line visual subtitle can be compared against a single normalized target string.

This avoids incorrectly rejecting a match simply because the subtitle's visual layout differs from the target input.

---

# 10. OCR Confidence

As with speech recognition, OCR confidence is incorporated into the matching score.

The implemented OCR score is:

```text
fuzzy_similarity *
(0.65 + 0.35 * sqrt(mean_OCR_confidence))
```

This combines:

```text
text similarity
+
OCR recognition confidence
```

rather than treating every OCR string as equally reliable.

The target threshold can be configured from the command line using:

```text
--threshold
```

The default threshold is:

```text
80
```

on the application's 0–100 command-line scale.

---

# 11. Coarse-to-Fine OCR Search

The OCR path does not attempt to process every frame of a long video immediately.

Instead, it uses a temporal search strategy.

The first pass performs relatively sparse sampling.

The configured default coarse interval is:

```text
2.0 seconds
```

If the first pass does not produce an adequate match, the system can perform a denser fallback pass.

The default fallback interval is:

```text
0.5 seconds
```

Conceptually:

```text
Entire video
     |
     v
Coarse sampling
     |
     v
Potential matching region
     |
     v
Denser sampling
     |
     v
Local frame refinement
     |
     v
First stable match
```

This reduces the amount of OCR computation while still providing a mechanism to search more densely when the coarse pass is insufficient.

---

# 12. Exact Visual Frame Localization

Once OCR identifies a promising area, the system performs local refinement.

The goal is not simply:

> "Find a frame where the target exists."

The goal is to identify the earliest reliable frame supported by the visual recognition evidence.

Conceptually:

```text
Candidate time range
       |
       v
Sequential frames
       |
       v
OCR + fuzzy matching
       |
       v
Stable matching evidence
       |
       v
Earliest reliable frame
```

The number of consecutive matching frames required for stable refinement is configurable through:

```text
--stable-frames
```

The default is:

```text
2
```

This helps prevent a single erroneous OCR result from being treated as the final answer.

---

# 13. OCR Region Selection

The default OCR region is the full video frame.

This is important because the application should not assume that dialogue always appears at the bottom of the screen.

The CLI provides optional region modes:

```text
full
bottom
top
```

The default is:

```text
full
```

The `bottom` and `top` modes can be used when the evaluator knows that the relevant text is constrained to a particular part of the frame.

This is treated as a performance optimization rather than a universal assumption about subtitle placement.

---

# 14. Image Processing

The image-processing layer is deliberately kept lightweight.

The application can resize frames before OCR and limit the maximum OCR image width using:

```text
--max-ocr-width
```

The default maximum OCR width is:

```text
1280
```

The purpose is to reduce unnecessary OCR computation on very large frames while preserving enough resolution for text recognition.

The original frame is retained for final output so that the saved result represents the actual video frame rather than an OCR-specific transformed version.

---

# 15. Media Acquisition

The application accepts both:

```text
public HTTP(S) video URLs
local video files
```

For URL inputs, `yt-dlp` is used to obtain the required media.

The media layer is separated from recognition so that the rest of the application does not need to handle website-specific acquisition details.

The resulting media is then made available for:

```text
audio extraction
video decoding
frame access
timestamp handling
```

The implementation uses local media-processing libraries rather than requiring an external OCR or speech API.

---

# 16. Automatic Search Mode

The default mode is:

```text
auto
```

The high-level behavior is:

```text
                  Input video
                       |
                       v
                Speech recognition
                       |
                 Target matched?
                  /          \
                yes           no
                 |             |
                 v             v
             timestamp         OCR
                 |             |
                 |        target matched?
                 |          /       \
                 |        yes        no
                 |         |          |
                 +---------+----------+
                           |
                           v
                         Result
```

The speech path is therefore used as an efficient first attempt for spoken dialogue.

The OCR path remains available for cases where speech recognition cannot locate the target.

---

# 17. Why the System Does Not Use an LLM

No runtime LLM is required for the core recognition process.

The system uses deterministic/local components:

```text
faster-whisper
RapidOCR
RapidFuzz
media-processing libraries
```

This provides several benefits:

- reproducible behavior;
- no external API dependency;
- lower runtime cost;
- easier debugging;
- explainable matching decisions.

The speech recognizer is also not given the requested target phrase as a prompt.

It independently transcribes the audio, after which the application compares the transcription against the requested dialogue.

This avoids biasing the recognizer toward hallucinating the requested phrase.

---

# 18. Handling Uncertainty

Recognition systems can produce near matches without sufficient evidence to confidently report an exact result.

The implementation therefore distinguishes between successful, uncertain, and unsuccessful outcomes.

Conceptually:

```text
Strong evidence
      |
      v
    FOUND

Near / insufficient evidence
      |
      v
  UNCERTAIN

No meaningful evidence
      |
      v
 NOT_FOUND
```

In uncertain cases, the application preserves the available evidence instead of silently fabricating an exact answer.

This is especially important because the assessment explicitly requires the solution to explain how ambiguous or uncertain results are handled.

---

# 19. Why We Chose a Hybrid Approach

There are several possible ways to solve the problem.

### OCR-only

```text
Video
  |
  v
Sample frames
  |
  v
OCR
```

This works for visible text but can require substantial processing on long videos.

### Speech-only

```text
Audio
  |
  v
ASR
  |
  v
Timestamp
```

This is efficient for spoken dialogue but cannot detect text that is only visually present.

### Hybrid

```text
                 Video
                   |
          +--------+--------+
          |                 |
          v                 v
       Audio             Visual
          |                 |
          v                 v
       ASR               OCR
          |                 |
          +--------+--------+
                   |
                   v
              Localization
                   |
                   v
                 Result
```

The implemented system uses the hybrid approach because the two sources provide complementary evidence.

Speech recognition is particularly useful as a temporal index for spoken dialogue.

OCR provides an independent mechanism for visible text.

---

# 20. Engineering Trade-offs

The implementation intentionally avoids adding unnecessary components.

### Why faster-whisper?

It provides strong local speech recognition with timestamped words and integrates naturally with Python.

The important output for this application is not a perfect transcript of the entire video. It is sufficiently accurate recognized text plus useful temporal information.

### Why RapidOCR?

The OCR path needs to process video frames rather than clean document images.

RapidOCR provides local text detection and recognition with confidence information, which fits the visual search requirements.

### Why fuzzy matching?

Exact string equality is too fragile for ASR and OCR because both recognition systems can introduce small errors.

Fuzzy matching allows the system to tolerate realistic recognition variations.

### Why coarse-to-fine search?

Processing every frame of a long video with OCR is unnecessarily expensive.

Sparse temporal sampling followed by denser local refinement provides a better accuracy/performance trade-off.

### Why local models?

The application can run without requiring an external speech-recognition or OCR API.

This makes evaluation more reproducible and avoids network/API availability becoming a dependency of the recognition pipeline.

---

# 21. Important Robustness Decisions

The implementation avoids hardcoding the supplied assessment example.

The video URL is a runtime input.

The target dialogue is also a runtime input.

Therefore, the application can be executed against another video and another target phrase.

The implementation also avoids assuming:

- a particular video resolution;
- a single fixed frame rate;
- a particular subtitle position;
- an exact OCR spelling;
- an exact ASR transcription.

These properties can vary between evaluation videos.

---

# 22. Validation Strategy

Validation is performed at multiple levels.

### Unit-level validation

Deterministic components such as text normalization and matching can be tested without running a complete video search.

Examples include:

```text
case differences
punctuation differences
Unicode normalization
OCR spelling errors
ASR spelling errors
multi-line OCR text
weak matches
strong matches
```

### Media validation

The media layer is tested using actual video inputs to verify:

```text
URL acquisition
video decoding
audio access
frame access
timestamp/frame mapping
```

### Recognition validation

The speech and OCR paths are evaluated against representative inputs to determine whether the target can be recognized despite realistic recognition errors.

### End-to-end validation

Finally, the complete CLI is executed against actual video URLs and target dialogues.

This verifies that:

```text
CLI
  |
  v
Media acquisition
  |
  v
Recognition
  |
  v
Matching
  |
  v
Localization
  |
  v
Output
```

works as a complete system.

---

# 23. Current Default Configuration

The important defaults exposed by the CLI include:

```text
mode              = auto
threshold         = 80
ASR model         = base.en
language          = en
device            = cpu
compute type      = int8
coarse interval   = 2.0 seconds
fallback interval = 0.5 seconds
stable frames     = 2
OCR region        = full
max OCR width     = 1280
```

These are configuration choices rather than hardcoded assumptions about the input video.

They can be changed through command-line arguments when the evaluator or environment requires different behavior.

---

# 24. Final Design Principle

The central design principle is:

> **Use inexpensive temporal information to narrow the search, use recognition models to establish textual evidence, and perform localized frame refinement before reporting the result.**

The system therefore separates the problem into:

```text
1. Acquire the media
       |
2. Determine where the dialogue may occur
       |
3. Match the requested dialogue against recognized text
       |
4. Localize the relevant frame
       |
5. Preserve the actual recognized evidence
       |
6. Return the result and output artifacts
```

This approach avoids relying on a single recognition mechanism and provides a practical balance between accuracy, processing cost, reproducibility, and explainability.