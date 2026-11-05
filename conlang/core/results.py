from dataclasses import dataclass, field
from typing import Literal

from .words import Word

NoteLevel = Literal["notice", "info"]


class Note(str):
    """A rule message; `level` is "notice" (lossy or unexpected) or "info" (hidden by default)."""

    level: NoteLevel = "notice"

    def __new__(cls, text: str, level: NoteLevel = "notice"):
        note = super().__new__(cls, text)
        note.level = level
        return note


def info(text: str) -> Note:
    return Note(text, "info")


def is_info(rule: str) -> bool:
    return getattr(rule, "level", "notice") == "info"


@dataclass
class ClauseResult:
    source_text: str
    words: list[Word]
    rules: list[str] = field(default_factory=list)
    fallback_spans: list[tuple[int, int]] = field(default_factory=list)
