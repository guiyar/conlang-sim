"""Segment-based morphology and a single final phonotactic pass."""

from dataclasses import dataclass, field
from difflib import SequenceMatcher

VALID_KINDS = {"root", "prefix", "suffix", "infix", "clitic", "particle", "reduplicant", "epenthetic"}


@dataclass
class Morpheme:
    segments: tuple[str, ...]
    gloss: str
    kind: str
    position: int | None = None

    def __post_init__(self):
        self.segments = tuple(self.segments)
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
    def segments(self):
        output = []
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
        self.morphemes.insert(root_index, Morpheme(copied, "RED", "reduplicant"))

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
        insertions = []
        for operation, start, _, target_start, target_end in matcher.get_opcodes():
            if operation == "insert":
                insertions.extend((start, segment) for segment in segments[target_start:target_end])
        for position, segment in reversed(insertions):
            offset = 0
            inserted = False
            for index, morpheme in enumerate(self.morphemes):
                if offset == position:
                    self.morphemes.insert(index, Morpheme((segment,), "EPENTH", "epenthetic"))
                    inserted = True
                    break
                offset += len(morpheme.segments)
                if offset == position:
                    self.morphemes.insert(index + 1, Morpheme((segment,), "EPENTH", "epenthetic"))
                    inserted = True
                    break
            if not inserted and position >= offset:
                self.morphemes.append(Morpheme((segment,), "EPENTH", "epenthetic"))
            elif not inserted:
                target = next((m for m in self.morphemes if m.kind == "root"), self.morphemes[0])
                target.segments = tuple(target.segments) + (segment,)
        self._surface_form = "".join(segments)
        return self._surface_form

    def segmented(self):
        return "-".join("".join(m.segments) for m in self.morphemes)

    def gloss(self):
        return "-".join(m.gloss for m in self.morphemes)