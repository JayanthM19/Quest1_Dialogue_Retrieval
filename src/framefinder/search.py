from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import cv2
import numpy as np

from .matcher import match_dialogue
from .models import MatchEvidence, SearchResult, VideoMetadata
from .ocr import OCREngine
from .video import VideoReader, format_timestamp, prepare_for_ocr

ProgressCallback = Callable[[str, int, int, float], None]


@dataclass(frozen=True)
class LocatedFrame:
    frame_number: int
    frame: np.ndarray
    evidence: MatchEvidence
    exact: bool


class DialogueFrameFinder:
    def __init__(
        self,
        ocr: OCREngine,
        *,
        threshold: float = 78.0,
        coarse_interval_seconds: float = 2.0,
        fallback_interval_seconds: float = 0.5,
        stable_frames: int = 2,
        region: str = "full",
        max_ocr_width: int = 1280,
        progress: ProgressCallback | None = None,
    ) -> None:
        if not 0 < threshold <= 100:
            raise ValueError("threshold must be in (0, 100]")
        if coarse_interval_seconds <= 0:
            raise ValueError("coarse_interval_seconds must be positive")
        if fallback_interval_seconds < 0:
            raise ValueError("fallback_interval_seconds cannot be negative")
        if stable_frames < 1:
            raise ValueError("stable_frames must be at least 1")
        self.ocr = ocr
        self.threshold = threshold
        self.coarse_interval_seconds = coarse_interval_seconds
        self.fallback_interval_seconds = fallback_interval_seconds
        self.stable_frames = stable_frames
        self.region = region
        self.max_ocr_width = max_ocr_width
        self.progress = progress

    def locate(self, video_path: Path, dialogue: str) -> tuple[LocatedFrame | None, VideoMetadata, dict]:
        if not dialogue.strip():
            raise ValueError("dialogue cannot be empty")

        with VideoReader(video_path) as reader:
            metadata = reader.metadata
            coarse_step = max(1, round(metadata.fps * self.coarse_interval_seconds))
            coarse_indices = list(_sample_indices(metadata.frame_count, coarse_step))
            checked: set[int] = set()
            diagnostics = {
                "coarse_interval_seconds": self.coarse_interval_seconds,
                "fallback_interval_seconds": self.fallback_interval_seconds,
                "threshold": self.threshold,
                "region": self.region,
                "coarse_samples": 0,
                "fallback_samples": 0,
                "fine_frames": 0,
                "best_score": 0.0,
                "best_frame": None,
            }

            candidate, best = self._scan_indices(
                reader,
                dialogue,
                coarse_indices,
                "coarse",
                diagnostics,
                checked,
            )
            active_step = coarse_step

            if candidate is None and self.fallback_interval_seconds > 0:
                fallback_step = max(
                    1, round(metadata.fps * self.fallback_interval_seconds)
                )
                if fallback_step < coarse_step:
                    fallback_indices = [
                        index
                        for index in _sample_indices(metadata.frame_count, fallback_step)
                        if index not in checked
                    ]
                    fallback_candidate, fallback_best = self._scan_indices(
                        reader,
                        dialogue,
                        fallback_indices,
                        "fallback",
                        diagnostics,
                        checked,
                    )
                    candidate = fallback_candidate
                    best = _better(best, fallback_best)
                    active_step = fallback_step

            if candidate is None:
                if best is not None and best.evidence.score >= self.threshold - 10:
                    # Preserve a useful near-match so callers can report uncertainty.
                    return LocatedFrame(
                        best.frame_number,
                        reader.read(best.frame_number),
                        best.evidence,
                        exact=False,
                    ), metadata, diagnostics
                return None, metadata, diagnostics

            start = max(0, candidate.frame_number - active_step)
            end = min(
                metadata.frame_count - 1,
                candidate.frame_number + self.stable_frames - 1,
            )
            exact = self._refine(reader, dialogue, start, end, diagnostics)
            if exact is not None:
                return exact, metadata, diagnostics

            # A random-access coarse read can occasionally differ from sequential
            # decoding. Return it explicitly as uncertain instead of claiming exactness.
            return LocatedFrame(
                candidate.frame_number,
                reader.read(candidate.frame_number),
                candidate.evidence,
                exact=False,
            ), metadata, diagnostics

    def _scan_indices(
        self,
        reader: VideoReader,
        dialogue: str,
        indices: Iterable[int],
        stage: str,
        diagnostics: dict,
        checked: set[int],
    ) -> tuple[LocatedFrame | None, LocatedFrame | None]:
        values = list(indices)
        best: LocatedFrame | None = None
        for position, frame_number in enumerate(values, start=1):
            frame = reader.read(frame_number)
            evidence = self._evaluate(frame, dialogue)
            checked.add(frame_number)
            diagnostics[f"{stage}_samples"] += 1
            if evidence.score > diagnostics["best_score"]:
                diagnostics["best_score"] = round(evidence.score, 3)
                diagnostics["best_frame"] = frame_number
            current = LocatedFrame(frame_number, frame, evidence, exact=False)
            best = _better(best, current)
            if self.progress:
                self.progress(stage, position, len(values), evidence.score)
            if evidence.score >= self.threshold:
                return current, best
        return None, best

    def _refine(
        self,
        reader: VideoReader,
        dialogue: str,
        start: int,
        end: int,
        diagnostics: dict,
    ) -> LocatedFrame | None:
        run: list[LocatedFrame] = []
        total = end - start + 1
        for position, (frame_number, frame) in enumerate(
            reader.iter_range(start, end), start=1
        ):
            evidence = self._evaluate(frame, dialogue)
            diagnostics["fine_frames"] += 1
            if self.progress:
                self.progress("fine", position, total, evidence.score)
            if evidence.score >= self.threshold:
                run.append(LocatedFrame(frame_number, frame.copy(), evidence, exact=True))
                if len(run) >= self.stable_frames:
                    return run[0]
            else:
                run.clear()
        return None

    def _evaluate(self, frame: np.ndarray, dialogue: str) -> MatchEvidence:
        prepared = prepare_for_ocr(
            frame,
            region=self.region,
            max_width=self.max_ocr_width,
        )
        return match_dialogue(dialogue, self.ocr.read(prepared))


def build_search_result(
    *,
    located: LocatedFrame | None,
    metadata: VideoMetadata,
    dialogue: str,
    source: str,
    image_path: Path | None,
    diagnostics: dict,
) -> SearchResult:
    if located is None:
        return SearchResult(
            status="not_found",
            target_text=dialogue,
            source=source,
            video_path=str(metadata.path),
            recognition_method="ocr",
            fps=metadata.fps,
            notes=[
                "No sampled frame reached the configured match threshold.",
                "Try a smaller interval, a lower threshold, or a different OCR region.",
            ],
            diagnostics=diagnostics,
        )

    seconds = located.frame_number / metadata.fps
    status = "found" if located.exact else "uncertain"
    notes = []
    if not located.exact:
        notes.append(
            "A near/coarse match was retained, but frame-level stability verification failed."
        )
    return SearchResult(
        status=status,
        target_text=dialogue,
        source=source,
        video_path=str(metadata.path),
        timestamp_seconds=seconds,
        timestamp=format_timestamp(seconds),
        frame_number=located.frame_number,
        extracted_text=located.evidence.matched_text,
        recognition_method="ocr",
        confidence=round(located.evidence.score, 3),
        fuzzy_score=round(located.evidence.fuzzy_score, 3),
        recognizer_confidence=round(located.evidence.ocr_confidence, 5),
        output_image=str(image_path) if image_path else None,
        fps=metadata.fps,
        notes=notes,
        diagnostics=diagnostics,
    )


def save_frame(path: Path, frame: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), frame):
        raise OSError(f"Could not write frame image: {path}")


def _sample_indices(frame_count: int, step: int) -> Iterable[int]:
    yield from range(0, frame_count, step)
    if frame_count and (frame_count - 1) % step:
        yield frame_count - 1


def _better(
    left: LocatedFrame | None, right: LocatedFrame | None
) -> LocatedFrame | None:
    if left is None:
        return right
    if right is None:
        return left
    return right if right.evidence.score > left.evidence.score else left
