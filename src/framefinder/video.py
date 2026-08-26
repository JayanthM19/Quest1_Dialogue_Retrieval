from __future__ import annotations

from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

from .models import VideoMetadata


class VideoReadError(RuntimeError):
    """Raised when OpenCV cannot decode the supplied video."""


class VideoReader:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._capture = cv2.VideoCapture(str(path))
        if not self._capture.isOpened():
            raise VideoReadError(f"OpenCV could not open video: {path}")

        fps = float(self._capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(self._capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if fps <= 0 or frame_count <= 0 or width <= 0 or height <= 0:
            self.close()
            raise VideoReadError("Video metadata is missing or invalid.")
        self.metadata = VideoMetadata(path, fps, frame_count, width, height)

    def close(self) -> None:
        self._capture.release()

    def __enter__(self) -> "VideoReader":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def read(self, frame_number: int) -> np.ndarray:
        if frame_number < 0 or frame_number >= self.metadata.frame_count:
            raise VideoReadError(f"Frame {frame_number} is outside the video.")
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ok, frame = self._capture.read()
        if not ok or frame is None:
            raise VideoReadError(f"Could not decode frame {frame_number}.")
        return frame

    def iter_range(self, start: int, end_inclusive: int) -> Iterator[tuple[int, np.ndarray]]:
        start = max(0, start)
        end_inclusive = min(end_inclusive, self.metadata.frame_count - 1)
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, start)
        for frame_number in range(start, end_inclusive + 1):
            ok, frame = self._capture.read()
            if not ok or frame is None:
                break
            yield frame_number, frame


def prepare_for_ocr(
    frame: np.ndarray,
    *,
    region: str = "full",
    max_width: int = 1280,
) -> np.ndarray:
    if region == "bottom":
        y = int(frame.shape[0] * 0.45)
        frame = frame[y:, :]
    elif region == "top":
        y = int(frame.shape[0] * 0.55)
        frame = frame[:y, :]
    elif region != "full":
        raise ValueError(f"Unknown OCR region: {region}")

    width = frame.shape[1]
    if width > max_width:
        scale = max_width / width
        frame = cv2.resize(
            frame,
            (max_width, max(1, round(frame.shape[0] * scale))),
            interpolation=cv2.INTER_AREA,
        )
    return frame


def format_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
