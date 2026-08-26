from __future__ import annotations

from typing import Protocol

import numpy as np

from .models import OCRLine, OCRResult


class OCREngine(Protocol):
    def read(self, image: np.ndarray) -> OCRResult:
        """Extract positioned text lines from a BGR image."""


class RapidOCREngine:
    """Offline OCR backed by compact ONNX models bundled with RapidOCR."""

    def __init__(self) -> None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:  # pragma: no cover - dependency/setup failure
            raise RuntimeError(
                "rapidocr-onnxruntime is not installed. Run: python -m pip install -e ."
            ) from exc
        self._engine = RapidOCR()

    def read(self, image: np.ndarray) -> OCRResult:
        raw, _elapsed = self._engine(image)
        if not raw:
            return OCRResult()

        lines: list[OCRLine] = []
        for item in raw:
            if len(item) < 3:
                continue
            box, text, confidence = item[:3]
            points = tuple((float(point[0]), float(point[1])) for point in box)
            lines.append(
                OCRLine(
                    text=str(text),
                    confidence=float(confidence),
                    box=points,
                )
            )
        return OCRResult(tuple(_reading_order(lines)))


def _reading_order(lines: list[OCRLine]) -> list[OCRLine]:
    if not lines or any(not line.box for line in lines):
        return lines

    def geometry(line: OCRLine) -> tuple[float, float, float, float]:
        xs = [point[0] for point in line.box]
        ys = [point[1] for point in line.box]
        return min(xs), min(ys), max(xs), max(ys)

    # OCR boxes on the same visual row often have slightly different top edges.
    # Cluster by vertical centre before sorting left-to-right; a simple (y, x)
    # sort can incorrectly reverse words from one subtitle line.
    rows: list[list[OCRLine]] = []
    for line in sorted(lines, key=lambda item: sum(p[1] for p in item.box) / len(item.box)):
        left, top, right, bottom = geometry(line)
        center = (top + bottom) / 2
        height = max(1.0, bottom - top)
        if rows:
            row_geometries = [geometry(item) for item in rows[-1]]
            row_center = sum((g[1] + g[3]) / 2 for g in row_geometries) / len(
                row_geometries
            )
            row_height = max(1.0, max(g[3] - g[1] for g in row_geometries))
            if abs(center - row_center) <= 0.55 * max(height, row_height):
                rows[-1].append(line)
                continue
        rows.append([line])

    ordered: list[OCRLine] = []
    for row in rows:
        ordered.extend(sorted(row, key=lambda item: geometry(item)[0]))
    return ordered
