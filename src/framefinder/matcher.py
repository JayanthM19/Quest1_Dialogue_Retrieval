from __future__ import annotations

import math
import re
import unicodedata

from rapidfuzz import fuzz

from .models import MatchEvidence, OCRLine, OCRResult

_NON_WORD = re.compile(r"[^\w\s]+", flags=re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = _NON_WORD.sub(" ", value)
    return _WHITESPACE.sub(" ", value).strip()


def match_dialogue(target: str, result: OCRResult) -> MatchEvidence:
    normalized_target = normalize_text(target)
    usable = [line for line in result.lines if normalize_text(line.text)]
    if not normalized_target or not usable:
        return MatchEvidence(0.0, 0.0, 0.0, "", result.text, result.lines)

    # Dialogue may span multiple OCR boxes. Test every consecutive group while
    # retaining spatial order; cap the group size to avoid combinatorial growth.
    best_fuzzy = 0.0
    best_text = ""
    best_lines: list[OCRLine] = []
    max_group = min(6, len(usable))
    for start in range(len(usable)):
        for size in range(1, max_group + 1):
            group = usable[start : start + size]
            if len(group) != size:
                break
            candidate = " ".join(line.text.strip() for line in group)
            normalized_candidate = normalize_text(candidate)
            if not normalized_candidate:
                continue

            # Ratio (rather than partial-ratio) intentionally penalizes unrelated
            # text surrounding a query. Since we test every consecutive OCR-line
            # group, the target-sized group can still win inside a busy frame.
            fuzzy = float(fuzz.ratio(normalized_target, normalized_candidate))

            if fuzzy > best_fuzzy:
                best_fuzzy = fuzzy
                best_text = candidate
                best_lines = group

    if not best_lines:
        return MatchEvidence(0.0, 0.0, 0.0, "", result.text, result.lines)

    weights = [max(1, len(normalize_text(line.text))) for line in best_lines]
    confidence = sum(
        line.confidence * weight for line, weight in zip(best_lines, weights)
    ) / sum(weights)

    # OCR confidence moderates rather than dominates the edit-similarity score.
    # This tolerates compression/fade-in while still penalizing weak OCR guesses.
    combined = best_fuzzy * (0.65 + 0.35 * math.sqrt(max(0.0, confidence)))
    return MatchEvidence(
        score=combined,
        fuzzy_score=best_fuzzy,
        ocr_confidence=confidence,
        matched_text=best_text,
        all_text=result.text,
        lines=tuple(best_lines),
    )
