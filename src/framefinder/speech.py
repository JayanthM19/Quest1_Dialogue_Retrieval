from __future__ import annotations

import math
from collections import deque
from pathlib import Path

from rapidfuzz import fuzz

from .matcher import normalize_text
from .models import SpeechMatch, TranscriptWord


class TranscriptionError(RuntimeError):
    """Raised when the speech recognizer cannot process a media file."""


class StreamingSpeechMatcher:
    """Match a target against chronological ASR words without storing a transcript."""

    def __init__(self, target: str, threshold: float) -> None:
        self.target = normalize_text(target)
        self.target_tokens = self.target.split()
        if not self.target_tokens:
            raise ValueError("dialogue cannot be empty")
        self.threshold = threshold
        self._history: deque[TranscriptWord] = deque(
            maxlen=len(self.target_tokens) + 1
        )
        self.best: SpeechMatch | None = None

    def push(self, word: TranscriptWord) -> SpeechMatch | None:
        self._history.append(word)
        values = list(self._history)
        target_count = len(self.target_tokens)
        matches: list[SpeechMatch] = []

        for size in {max(1, target_count - 1), target_count, target_count + 1}:
            if len(values) < size:
                continue
            window = values[-size:]
            normalized_words = [normalize_text(item.text) for item in window]
            if not normalized_words[0] or not normalized_words[-1]:
                continue

            # Missing the first word would shift the reported onset forward even
            # when the rest of a long phrase is similar. Guard both boundaries.
            if fuzz.ratio(self.target_tokens[0], normalized_words[0].split()[0]) < 65:
                continue
            if fuzz.ratio(self.target_tokens[-1], normalized_words[-1].split()[-1]) < 65:
                continue

            candidate = " ".join(item.text.strip() for item in window).strip()
            fuzzy_score = float(fuzz.ratio(self.target, normalize_text(candidate)))
            probability = sum(max(0.0, item.probability) for item in window) / len(
                window
            )
            score = fuzzy_score * (0.75 + 0.25 * math.sqrt(probability))
            matches.append(
                SpeechMatch(
                    start_seconds=window[0].start,
                    end_seconds=window[-1].end,
                    text=candidate,
                    score=score,
                    fuzzy_score=fuzzy_score,
                    asr_confidence=probability,
                    exact=score >= self.threshold,
                )
            )

        if not matches:
            return None
        current = max(matches, key=lambda item: item.score)
        if self.best is None or current.score > self.best.score:
            self.best = current
        return current if current.exact else None


class FasterWhisperEngine:
    """Offline speech recognition with word timestamps."""

    def __init__(
        self,
        *,
        model_name: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        download_root: Path | None = None,
    ) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - dependency/setup failure
            raise TranscriptionError(
                "faster-whisper is not installed. Run: python -m pip install -e ."
            ) from exc

        try:
            self._model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                download_root=str(download_root) if download_root else None,
            )
        except Exception as exc:  # model download/runtime failures vary by backend
            raise TranscriptionError(f"Could not load ASR model '{model_name}': {exc}") from exc
        self.model_name = model_name

    def find(
        self,
        media_path: Path,
        dialogue: str,
        *,
        threshold: float = 80.0,
        language: str | None = "en",
    ) -> tuple[SpeechMatch | None, dict]:
        matcher = StreamingSpeechMatcher(dialogue, threshold)
        diagnostics = {
            "mode": "speech",
            "model": self.model_name,
            "language": language or "auto",
            "threshold": threshold,
            "segments_processed": 0,
            "words_processed": 0,
            "best_score": 0.0,
        }

        try:
            segments, info = self._model.transcribe(
                str(media_path),
                language=language,
                beam_size=5,
                word_timestamps=True,
                vad_filter=True,
                condition_on_previous_text=True,
            )
            diagnostics["detected_language"] = info.language
            diagnostics["language_probability"] = round(
                float(info.language_probability), 5
            )
            for segment in segments:
                diagnostics["segments_processed"] += 1
                for raw in segment.words or ():
                    word = TranscriptWord(
                        text=str(raw.word),
                        start=float(raw.start),
                        end=float(raw.end),
                        probability=float(raw.probability),
                    )
                    diagnostics["words_processed"] += 1
                    match = matcher.push(word)
                    if matcher.best:
                        diagnostics["best_score"] = round(matcher.best.score, 3)
                    if match is not None:
                        return match, diagnostics
        except Exception as exc:
            # A progressively downloaded MP4 may end mid-packet. If useful words
            # were decoded first, retain their evidence; otherwise surface the error.
            if diagnostics["words_processed"] == 0:
                raise TranscriptionError(f"Speech transcription failed: {exc}") from exc
            diagnostics["decoder_warning"] = str(exc)

        best = matcher.best
        if best is not None and best.score >= threshold - 10:
            return best, diagnostics
        return None, diagnostics
