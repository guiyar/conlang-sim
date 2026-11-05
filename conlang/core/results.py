from dataclasses import dataclass, field


class Note(str):
    """A rule message; `level` is "notice" (lossy or unexpected) or "info" (hidden by default)."""

    level: str = "notice"

    def __new__(cls, text, level="notice"):
        note = super().__new__(cls, text)
        note.level = level
        return note


def info(text):
    return Note(text, "info")


def is_info(rule):
    return getattr(rule, "level", "notice") == "info"


@dataclass
class ClauseResult:
    source_text: str
    words: list
    rules: list = field(default_factory=list)
    fallback_spans: list = field(default_factory=list)
