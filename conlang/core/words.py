"""Segment-based morphology and a single final phonotactic pass."""

from dataclasses import dataclass, field

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


@dataclass(frozen=True)
class SurfaceInsertion:
    position: int
    segment: str
    reason: str


@dataclass(frozen=True)
class SurfaceResult:
    segments: tuple[str, ...]
    insertions: tuple[SurfaceInsertion, ...] = ()


@dataclass(frozen=True)
class SurfaceEdit:
    anchor_morpheme: int
    anchor_segment: int
    inserted_segment: str
    reason: str


@dataclass(frozen=True)
class RealizedMorpheme:
    segments: tuple[str, ...]
    gloss: str
    kind: str
    position: int | None
    sources: tuple[int, ...]


@dataclass(frozen=True)
class RealizedWord:
    surface_form: str
    segments: tuple[str, ...]
    segmented_form: str
    gloss_form: str
    morphemes: tuple[RealizedMorpheme, ...]
    surface_edits: tuple[SurfaceEdit, ...]
    sources: tuple[int, ...]
    notes: tuple[str, ...]
    literal: bool

    def surface(self):
        return self.surface_form

    def segmented(self):
        return self.segmented_form

    def gloss(self):
        return self.gloss_form


@dataclass
class Word:
    morphemes: list[Morpheme]
    notes: list[str] = field(default_factory=list)
    literal: bool = False
    _realized: RealizedWord | None = field(default=None, init=False, repr=False)

    @property
    def realized(self):
        return self._realized

    @property
    def sources(self):
        if self._realized is not None:
            return self._realized.sources
        return tuple(sorted({i for m in self.morphemes for i in m.sources}))

    @property
    def segments(self):
        if self._realized is not None:
            return self._realized.segments
        return tuple(
            self.morphemes[morpheme].segments[segment]
            for morpheme, segment in self._segment_layout()
        )

    def _morphology_groups(self):
        groups: list[tuple[int, ...]] = []
        index = 0
        while index < len(self.morphemes):
            morpheme = self.morphemes[index]
            following = self.morphemes[index + 1] if index + 1 < len(self.morphemes) else None
            if morpheme.kind == "root" and following is not None and following.kind == "infix":
                groups.append((index, index + 1))
                index += 2
            else:
                groups.append((index,))
                index += 1
        return tuple(groups)

    def _segment_layout(self):
        layout: list[tuple[int, int]] = []
        for group in self._morphology_groups():
            if len(group) == 2:
                root_index, infix_index = group
                root = self.morphemes[root_index]
                infix = self.morphemes[infix_index]
                position = infix.position if infix.position is not None else 1
                split = min(position, len(root.segments))
                layout.extend((root_index, local) for local in range(split))
                layout.extend((infix_index, local) for local in range(len(infix.segments)))
                layout.extend((root_index, local) for local in range(split, len(root.segments)))
            else:
                morpheme_index = group[0]
                layout.extend(
                    (morpheme_index, local)
                    for local in range(len(self.morphemes[morpheme_index].segments))
                )
        return layout

    def _ensure_constructing(self):
        if self._realized is not None:
            raise RuntimeError("cannot modify a realized word")

    def add_prefix(self, morpheme):
        self._ensure_constructing()
        self.morphemes.insert(0, morpheme)

    def add_suffix(self, morpheme):
        self._ensure_constructing()
        self.morphemes.append(morpheme)

    def add_infix(self, morpheme, onset_length=1):
        self._ensure_constructing()
        roots = [i for i, m in enumerate(self.morphemes) if m.kind == "root"]
        if not roots or not 0 <= onset_length <= len(self.morphemes[roots[0]].segments):
            self.notes.append(f"infix {morpheme.gloss} fell back to suffixation")
            self.add_suffix(
                Morpheme(morpheme.segments, morpheme.gloss, "suffix", sources=morpheme.sources)
            )
            return
        morpheme.position = onset_length
        self.morphemes.insert(roots[0] + 1, morpheme)

    def reduplicate(self, partial=False, syllabify=None):
        self._ensure_constructing()
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
        self._ensure_constructing()
        self.morphemes.append(morpheme)

    def realize(self, validator=None, epenthetic_vowel="a"):
        if self._realized is not None:
            return self._realized
        original = list(self.segments)
        segments = list(original)
        insertions: tuple[SurfaceInsertion, ...] = ()
        if validator is not None:
            result = validator(segments, self.notes, epenthetic_vowel)
            if isinstance(result, SurfaceResult):
                segments = list(result.segments)
                insertions = result.insertions
            else:
                segments = list(result)
                if segments != original:
                    raise TypeError(
                        "surface validators that insert segments must return SurfaceResult"
                    )
        expected_segments = list(original)
        for insertion in insertions:
            if not 0 <= insertion.position <= len(expected_segments):
                raise ValueError(
                    "surface insertion position is outside the current segment sequence"
                )
            expected_segments.insert(insertion.position, insertion.segment)
        if expected_segments != segments:
            raise ValueError("surface insertion records do not match the returned segments")

        applied_edits: list[SurfaceEdit] = []
        for insertion in insertions:
            layout = self._segment_layout()
            if insertion.position < len(layout):
                morpheme_index, local_index = layout[insertion.position]
            elif layout:
                morpheme_index, local_index = layout[-1]
                local_index += 1
            else:
                raise ValueError("cannot anchor a surface insertion to an empty word")
            target = self.morphemes[morpheme_index]
            target.segments = (
                target.segments[:local_index] + (insertion.segment,) + target.segments[local_index:]
            )
            applied_edits.append(
                SurfaceEdit(
                    morpheme_index,
                    local_index,
                    insertion.segment,
                    insertion.reason,
                )
            )
            if target.kind == "root" and morpheme_index + 1 < len(self.morphemes):
                following = self.morphemes[morpheme_index + 1]
                if following.kind == "infix" and local_index <= (following.position or 0):
                    following.position = (following.position or 0) + 1
        surface_form = "".join(self.segments)
        self._realized = RealizedWord(
            surface_form,
            tuple(self.segments),
            self._segmented_form(),
            self._gloss_form(),
            tuple(
                RealizedMorpheme(
                    morpheme.segments,
                    morpheme.gloss,
                    morpheme.kind,
                    morpheme.position,
                    morpheme.sources,
                )
                for morpheme in self.morphemes
            ),
            tuple(applied_edits),
            self.sources,
            tuple(self.notes),
            self.literal,
        )
        return self._realized

    def surface(self, validator=None, epenthetic_vowel="a"):
        return self.realize(validator, epenthetic_vowel).surface()

    def segmented(self):
        if self._realized is not None:
            return self._realized.segmented()
        return self._segmented_form()

    def _segmented_form(self):
        parts = []
        for group in self._morphology_groups():
            if len(group) == 2:
                root = self.morphemes[group[0]]
                infix = self.morphemes[group[1]]
                position = infix.position if infix.position is not None else 1
                part = (
                    "".join(root.segments[:position])
                    + "<"
                    + "".join(infix.segments)
                    + ">"
                    + "".join(root.segments[position:])
                )
                parts.append(part)
            else:
                parts.append("".join(self.morphemes[group[0]].segments))
        return "-".join(parts)

    def gloss(self):
        if self._realized is not None:
            return self._realized.gloss()
        return self._gloss_form()

    def _gloss_form(self):
        parts = []
        for group in self._morphology_groups():
            if len(group) == 2:
                root = self.morphemes[group[0]]
                infix = self.morphemes[group[1]]
                parts.append(f"{root.gloss}<{infix.gloss}>")
            else:
                parts.append(self.morphemes[group[0]].gloss)
        return "-".join(parts)

    @property
    def morpheme_count(self):
        import re

        return len(re.findall(r"<[^<>]+>|[^<>-]+", self.gloss()))
