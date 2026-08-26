from framefinder.models import OCRLine
from framefinder.ocr import _reading_order


def test_reading_order_clusters_boxes_on_same_visual_line() -> None:
    right = OCRLine(
        "mind rebels at stagnation",
        0.99,
        ((161, 160), (913, 165), (913, 230), (161, 225)),
    )
    left = OCRLine(
        "My",
        0.99,
        ((72, 165), (158, 171), (155, 229), (69, 224)),
    )

    assert [line.text for line in _reading_order([right, left])] == [
        "My",
        "mind rebels at stagnation",
    ]
