from dataclasses import dataclass, field


@dataclass
class ClauseResult:
    source_text: str
    words: list
    rules: list = field(default_factory=list)
    fallback_spans: list = field(default_factory=list)