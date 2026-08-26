from framefinder.models import TranscriptWord
from framefinder.speech import StreamingSpeechMatcher


def _word(text: str, index: int, probability: float = 0.95) -> TranscriptWord:
    return TranscriptWord(text, index * 0.4, index * 0.4 + 0.3, probability)


def test_streaming_speech_match_preserves_first_word_timestamp() -> None:
    matcher = StreamingSpeechMatcher("My mind rebels at stagnation", threshold=80)
    words = [
        _word("unrelated", 0),
        _word("My", 1),
        _word("mind", 2),
        _word("rebels", 3),
        _word("at", 4),
        _word("stagnation.", 5),
    ]

    found = None
    for word in words:
        found = matcher.push(word) or found

    assert found is not None
    assert found.exact is True
    assert found.start_seconds == 0.4
    assert found.text == "My mind rebels at stagnation."


def test_speech_match_rejects_suffix_missing_target_onset() -> None:
    matcher = StreamingSpeechMatcher("My mind rebels at stagnation", threshold=80)
    for index, text in enumerate("mind rebels at stagnation".split()):
        assert matcher.push(_word(text, index)) is None
