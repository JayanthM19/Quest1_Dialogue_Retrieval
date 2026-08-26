from framefinder.matcher import match_dialogue, normalize_text
from framefinder.models import OCRLine, OCRResult


def test_normalize_text_ignores_case_punctuation_and_spacing() -> None:
    assert normalize_text("  My MIND—rebels, at stagnation! ") == (
        "my mind rebels at stagnation"
    )


def test_matches_dialogue_split_across_ocr_lines() -> None:
    ocr = OCRResult(
        (
            OCRLine("unrelated title", 0.95),
            OCRLine("My mind rebels", 0.92),
            OCRLine("at stagnatlon", 0.88),
            OCRLine("channel logo", 0.99),
        )
    )
    evidence = match_dialogue("My mind rebels at stagnation", ocr)

    assert evidence.score >= 85
    assert evidence.matched_text == "My mind rebels at stagnatlon"


def test_unrelated_text_has_low_score() -> None:
    evidence = match_dialogue(
        "My mind rebels at stagnation",
        OCRResult((OCRLine("Elementary, dear Watson", 0.99),)),
    )
    assert evidence.score < 50
