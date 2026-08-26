from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OCRLine:
    text: str
    confidence: float
    box: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class OCRResult:
    lines: tuple[OCRLine, ...] = ()

    @property
    def text(self) -> str:
        return " ".join(line.text.strip() for line in self.lines if line.text.strip())


@dataclass(frozen=True)
class MatchEvidence:
    score: float
    fuzzy_score: float
    ocr_confidence: float
    matched_text: str
    all_text: str
    lines: tuple[OCRLine, ...] = ()


@dataclass(frozen=True)
class VideoMetadata:
    path: Path
    fps: float
    frame_count: int
    width: int
    height: int

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.fps if self.fps else 0.0


@dataclass(frozen=True)
class TranscriptWord:
    text: str
    start: float
    end: float
    probability: float


@dataclass(frozen=True)
class SpeechMatch:
    start_seconds: float
    end_seconds: float
    text: str
    score: float
    fuzzy_score: float
    asr_confidence: float
    exact: bool


@dataclass
class SearchResult:
    status: str
    target_text: str
    source: str
    video_path: str
    timestamp_seconds: float | None = None
    timestamp: str | None = None
    frame_number: int | None = None
    frame_number_base: int = 0
    extracted_text: str = ""
    recognition_method: str = ""
    confidence: float = 0.0
    fuzzy_score: float = 0.0
    recognizer_confidence: float = 0.0
    output_image: str | None = None
    fps: float | None = None
    notes: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
