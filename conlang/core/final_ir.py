"""Immutable snapshots of validated sentence IR for downstream realization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .ir import (
    ArgumentRelation,
    ArgumentRole,
    ClauseKind,
    ClauseLinkRelation,
    Definiteness,
    Degree,
    Demonstrative,
    ModifierKind,
    Mood,
    NounPhraseKind,
    Number,
    Polarity,
    PostModifierKind,
    Tense,
    TokenDisposition,
    Voice,
)


class FinalNote(str):
    _level: str

    def __new__(cls, text: str, level: str = "notice"):
        note = super().__new__(cls, text)
        object.__setattr__(note, "_level", level)
        return note

    @property
    def level(self):
        return self._level

    def __setattr__(self, name, value):
        raise AttributeError("finalized note is immutable")


@dataclass(frozen=True)
class FinalSourceToken:
    text: str
    lemma: str
    pos: str
    tag: str
    dep: str
    morph: Mapping[str, tuple[str, ...]]
    head_index: int | None
    index: int | None
    disposition: TokenDisposition | None
    disposition_reason: str | None


@dataclass(frozen=True)
class FinalModifier:
    text: str
    lemma: str
    kind: ModifierKind
    pos: str
    value: int | None
    literal: bool
    sub_modifiers: tuple[FinalModifier, ...]
    indices: tuple[int, ...]
    degree: Degree


@dataclass(frozen=True)
class FinalPossessor:
    np: FinalNounPhrase


@dataclass(frozen=True)
class FinalPostModifier:
    kind: PostModifierKind
    adposition: str | None
    np: FinalNounPhrase | None
    link: FinalClauseLink | None
    index: int | None


@dataclass(frozen=True)
class FinalCoordination:
    conj: FinalSourceToken | None
    np: FinalNounPhrase


@dataclass(frozen=True)
class FinalClauseLink:
    relation: ClauseLinkRelation
    marker: FinalSourceToken | None
    clause: FinalClause
    source_tokens: tuple[FinalSourceToken, ...]


@dataclass(frozen=True)
class FinalNounPhrase:
    head: str
    kind: NounPhraseKind
    number: Number
    demonstrative: Demonstrative
    person: str
    gender: str
    case: str
    modifiers: tuple[FinalModifier, ...]
    possessor: FinalPossessor | None
    post_modifiers: tuple[FinalPostModifier, ...]
    coordinated: tuple[FinalCoordination, ...]
    source_tokens: tuple[FinalSourceToken, ...]
    morphology: Mapping[str, tuple[str, ...]]
    surface: str | None
    pos: str
    definiteness: Definiteness
    numeral_value: int | None
    literal: bool
    head_indices: tuple[int, ...]
    determiner_index: int | None
    demonstrative_index: int | None
    predeterminers: tuple[FinalModifier, ...]
    adverbs: tuple[FinalModifier, ...]
    degree: Degree


@dataclass(frozen=True)
class FinalArgument:
    relation: ArgumentRelation
    role: ArgumentRole
    np: FinalNounPhrase
    source_dep: str
    source_tokens: tuple[FinalSourceToken, ...]
    preposition: str | None
    preposition_index: int | None


@dataclass(frozen=True)
class FinalClause:
    predicate: str
    predicate_pos: str
    kind: ClauseKind
    polarity: Polarity
    tense: Tense
    perfect: bool
    progressive: bool
    mood: Mood
    transitivity: bool
    voice: Voice
    arguments: tuple[FinalArgument, ...]
    adverbs: tuple[FinalModifier, ...]
    modifiers: tuple[FinalModifier, ...]
    fragments: tuple[tuple[str, ...], ...]
    source_tokens: tuple[FinalSourceToken, ...]
    argument_order: tuple[tuple[ArgumentRelation, str], ...]
    links: tuple[FinalClauseLink, ...]
    predicate_index: int | None
    modals: tuple[FinalModifier, ...]


@dataclass(frozen=True)
class FinalizedSentenceIR:
    clause: FinalClause
    source_text: str
    rules: tuple[str, ...]
    fragments: tuple[tuple[str, ...], ...]
    source_tokens: tuple[FinalSourceToken, ...]
    numeral_spans: tuple[tuple[int, int], ...]
