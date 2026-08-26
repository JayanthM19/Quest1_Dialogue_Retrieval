from pathlib import Path

import cv2
import numpy as np

from framefinder.models import OCRLine, OCRResult
from framefinder.search import DialogueFrameFinder, build_search_result

TARGET = "My mind rebels at stagnation"


class MarkerOCR:
    """Deterministic test OCR: a bright marker represents the target text."""

    def read(self, image: np.ndarray) -> OCRResult:
        if float(image.mean()) > 15:
            return OCRResult((OCRLine(TARGET, 0.99),))
        return OCRResult((OCRLine("unrelated", 0.99),))


def _make_video(path: Path, *, first_visible: int = 11) -> None:
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (160, 90)
    )
    assert writer.isOpened()
    try:
        for index in range(30):
            frame = np.zeros((90, 160, 3), dtype=np.uint8)
            if first_visible <= index <= 22:
                frame[:, :] = 255
            writer.write(frame)
    finally:
        writer.release()


def test_coarse_to_fine_search_returns_first_stable_frame(tmp_path: Path) -> None:
    video = tmp_path / "synthetic.avi"
    _make_video(video)
    finder = DialogueFrameFinder(
        MarkerOCR(),
        threshold=78,
        coarse_interval_seconds=0.5,
        fallback_interval_seconds=0,
        stable_frames=2,
    )

    located, metadata, diagnostics = finder.locate(video, TARGET)

    assert located is not None
    assert located.exact is True
    assert located.frame_number == 11
    result = build_search_result(
        located=located,
        metadata=metadata,
        dialogue=TARGET,
        source=str(video),
        image_path=tmp_path / "frame.png",
        diagnostics=diagnostics,
    )
    assert result.status == "found"
    assert result.timestamp == "00:00:01.100"
    assert result.frame_number_base == 0


def test_no_match_is_reported_without_fabricating_frame(tmp_path: Path) -> None:
    video = tmp_path / "synthetic.avi"
    _make_video(video, first_visible=99)
    finder = DialogueFrameFinder(
        MarkerOCR(),
        coarse_interval_seconds=0.5,
        fallback_interval_seconds=0,
    )

    located, _metadata, _diagnostics = finder.locate(video, TARGET)

    assert located is None
