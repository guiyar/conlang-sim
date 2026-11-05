"""Segment-based morphology and a single final phonotactic pass."""

from dataclasses import dataclass, field
from difflib import SequenceMatcher

VALID_KINDS = frozenset(
    {"root", "prefix", "suffix", "infix", "clitic", "particle", "reduplicant", "epenthetic"}
)


@dataclass
class Morpheme:
    segments: tuple[str, ...]
    gloss: str
    kind: str
    position: int | None = None
    sources: tuple[int, ...] = ()

    def __post_init__(self):
        self.segments = tuple(self.segments)
        self.sources = tuple(self.sources)
        if self.kind not in VALID_KINDS:
            raise ValueError(f"invalid morpheme kind: {self.kind}")


@dataclass
class Word:
    morphemes: list[Morpheme]
    notes: list[str] = field(default_factory=list)
    _surfaced: bool = False
    _surface_form: str | None = None
    literal: bool = False

    @property
    def sources(self):
        return tuple(sorted({i for m in self.morphemes for i in m.sources}))

    @property
    def segments(self):
        output: list[str] = []
        index = 0
        while index < len(self.morphemes):
            morpheme = self.morphemes[index]
            following = self.morphemes[index + 1] if index + 1 < len(self.morphemes) else None
            if morpheme.kind == "root" and following is not None and following.kind == "infix":
                position = following.position if following.position is not None else 1
                output.extend(morpheme.segments[:position])
                output.extend(following.segments)
                output.extend(morpheme.segments[position:])
                index += 2
            else:
                output.extend(morpheme.segments)
                index += 1
        return tuple(output)

    def add_prefix(self, morpheme):
        self.morphemes.insert(0, morpheme)

    def add_suffix(self, morpheme):
        self.morphemes.append(morpheme)

    def add_infix(self, morpheme, onset_length=1):
        roots = [i for i, m in enumerate(self.morphemes) if m.kind == "root"]
        if not roots or not 0 <= onset_length <= len(self.morphemes[roots[0]].segments):
            self.notes.append(f"infix {morpheme.gloss} fell back to suffixation")
            self.add_suffix(Morpheme(morpheme.segments, morpheme.gloss, "suffix"))
            return
        morpheme.position = onset_length
        self.morphemes.insert(roots[0] + 1, morpheme)

    def reduplicate(self, partial=False, syllabify=None):
        root_index = next((i for i, m in enumerate(self.morphemes) if m.kind == "root"), None)
        if root_index is None:
            self.notes.append("reduplication fell back: no root")
            return
        root = self.morphemes[root_index]
        copied = tuple((syllabify(root.segments)[0] if partial and syllabify else root.segments))
        self.morphemes.insert(
            root_index, Morpheme(copied, "RED", "reduplicant", sources=root.sources)
        )

    def cliticize(self, morpheme):
        self.morphemes.append(morpheme)

    def surface(self, validator=None, epenthetic_vowel="a"):
        if self._surfaced:
            return self._surface_form
        self._surfaced = True
        original = list(self.segments)
        segments = list(original)
        if validator is not None:
            segments = validator(segments, self.notes, epenthetic_vowel)
        matcher = SequenceMatcher(a=original, b=segments, autojunk=False)
        insertions: list[tuple[int, str]] = []
        for operation, start, _, target_start, target_end in matcher.get_opcodes():
            if operation == "insert":
                insertions.extend((start, segment) for segment in segments[target_start:target_end])
        for position, segment in reversed(insertions):
            layout: list[tuple[int, int]] = []
            index = 0
            while index < len(self.morphemes):
                morpheme = self.morphemes[index]
                following = self.morphemes[index + 1] if index + 1 < len(self.morphemes) else None
                if morpheme.kind == "root" and following is not None and following.kind == "infix":
                    infix_position = following.position if following.position is not None else 1
                    layout.extend(
                        (index, local)
                        for local in range(min(infix_position, len(morpheme.segments)))
                    )
                    layout.extend((index + 1, local) for local in range(len(following.segments)))
                    layout.extend(
                        (index, local)
                        for local in range(
                            min(infix_position, len(morpheme.segments)), len(morpheme.segments)
                        )
                    )
                    index += 2
                else:
                    layout.extend((index, local) for local in range(len(morpheme.segments)))
                    index += 1
            if position < len(layout):
                morpheme_index, local_index = layout[position]
            elif layout:
                morpheme_index, local_index = layout[-1]
                local_index += 1
            else:
                continue
            target = self.morphemes[morpheme_index]
            target.segments = (
                target.segments[:local_index] + (segment,) + target.segments[local_index:]
            )
            if target.kind == "root" and morpheme_index + 1 < len(self.morphemes):
                following = self.morphemes[morpheme_index + 1]
                if following.kind == "infix" and local_index <= (following.position or 0):
                    following.position = (following.position or 0) + 1
        self._surface_form = "".join(self.segments)
        return self._surface_form

    def segmented(self):
        parts = []
        index = 0
        while index < len(self.morphemes):
            morpheme = self.morphemes[index]
            following = self.morphemes[index + 1] if index + 1 < len(self.morphemes) else None
            if morpheme.kind == "root" and following is not None and following.kind == "infix":
                position = following.position if following.position is not None else 1
                part = (
                    "".join(morpheme.segments[:position])
                    + "<"
                    + "".join(following.segments)
                    + ">"
                    + "".join(morpheme.segments[position:])
                )
                parts.append(part)
                index += 2
            else:
                parts.append("".join(morpheme.segments))
                index += 1
        return "-".join(parts)

    def gloss(self):
        parts = []
        index = 0
        while index < len(self.morphemes):
            morpheme = self.morphemes[index]
            following = self.morphemes[index + 1] if index + 1 < len(self.morphemes) else None
            if morpheme.kind == "root" and following is not None and following.kind == "infix":
                parts.append(f"{morpheme.gloss}<{following.gloss}>")
                index += 2
            else:
                parts.append(morpheme.gloss)
                index += 1
        return "-".join(parts)

    @property
    def morpheme_count(self):
        import re

        return len(re.findall(r"<[^<>]+>|[^<>-]+", self.gloss()))
