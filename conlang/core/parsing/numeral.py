"""Recognition and normalization of supported English cardinal phrases."""

from types import MappingProxyType
from typing import Iterable

_ONES = MappingProxyType(
    {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
    }
)
_TENS = MappingProxyType(
    {
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
    }
)
_SCALES = MappingProxyType({"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000})
_NUMBER_WORDS = frozenset(_ONES) | frozenset(_TENS) | frozenset({"hundred", *_SCALES, "and", "a"})


def is_number_word(text: str) -> bool:
    return text.lower() in _NUMBER_WORDS


def numeral_value(texts: Iterable[str]) -> int | None:
    words = [
        part
        for text in texts
        for part in text.lower().replace("-", " ").split()
        if part in _NUMBER_WORDS
    ]
    if not any(
        word in _ONES or word in _TENS or word == "hundred" or word in _SCALES for word in words
    ):
        return None

    total = current = 0
    for word in words:
        if word in {"and", "a"}:
            continue
        if word in _ONES:
            current += _ONES[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == "hundred":
            current = max(current, 1) * 100
        else:
            total += max(current, 1) * _SCALES[word]
            current = 0
    value = total + current
    return value if 0 <= value < 1_000_000_000 else None
