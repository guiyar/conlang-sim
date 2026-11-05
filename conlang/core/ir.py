"""Language-independent parsed English representation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final, Literal, TypeAlias

UNSPECIFIED: Final = "UNSPECIFIED"

Tense: TypeAlias = Literal["past", "present", "future", "UNSPECIFIED"]
Polarity: TypeAlias = Literal["positive", "negative"]
Voice: TypeAlias = Literal["active", "passive"]
Mood: TypeAlias = Literal["declarative", "interrogative", "imperative"]
ClauseKind: TypeAlias = Literal[
    "verbal", "equational", "locative", "existential", "nominal", "rootless", "interjection"
]
NounPhraseKind: TypeAlias = Literal[
    "noun", "pronoun", "proper", "number", "demonstrative_pronoun", "wh_pronoun", "other_pronoun"
]
Number: TypeAlias = Literal["singular", "plural", "UNSPECIFIED"]
Demonstrative: TypeAlias = Literal["none", "proximal", "distal"]
Definiteness: TypeAlias = Literal["definite", "indefinite", "none", "UNSPECIFIED"]
Degree: TypeAlias = Literal["none", "comparative", "superlative"]
ModifierKind: TypeAlias = Literal["modifier", "predeterminer", "numeral", "ordinal", "modal"]
ArgumentRelation: TypeAlias = Literal["subject", "object", "indirect_object", "oblique", "fragment"]
ArgumentRole: TypeAlias = Literal["agent", "patient", "other"]
PostModifierKind: TypeAlias = Literal["prep", "clause"]
ClauseLinkRelation: TypeAlias = Literal["coordinate", "adverbial", "complement", "xcomp"]
TokenDisposition: TypeAlias = Literal["realized", "absorbed", "dropped"]

STRUCTURAL_FIELDS = frozenset(
    {
        "clause.predicate",
        "clause.predicate_pos",
        "clause.arguments",
        "clause.argument_order",
        "clause.kind",
        "clause.fragments",
        "clause.adverbs",
        "clause.links",
        "clause.source_tokens",
        "argument.preposition",
        "argument.source_dep",
        "argument.source_tokens",
        "np.head",
        "np.pos",
        "np.surface",
        "np.source_tokens",
        "np.morphology",
        "np.numeral_value",
        "np.literal",
        "np.head_indices",
        "np.determiner_index",
        "np.demonstrative_index",
        "np.predeterminers",
        "np.adverbs",
        "clause.modals",
        "modifier.degree",
        "modifier.indices",
        "modifier.lemma",
        "post_modifier.index",
        "argument.preposition_index",
        "clause.predicate_index",
        "np.post_modifiers",
        "np.coordinated",
        "modifier.pos",
        "modifier.value",
        "modifier.literal",
        "modifier.sub_modifiers",
        "source_token.disposition",
        "source_token.disposition_reason",
        "source_token.text",
        "source_token.lemma",
        "source_token.pos",
        "source_token.tag",
        "source_token.dep",
        "source_token.morph",
        "source_token.head_index",
        "source_token.index",
        "source_tokens",
        "rules",
        "post_modifier.kind",
        "post_modifier.adposition",
        "post_modifier.np",
        "post_modifier.link",
        "coordination.conj",
        "coordination.np",
        "clause_link.relation",
        "clause_link.marker",
        "clause_link.clause",
        "clause_link.source_tokens",
    }
)
VALID_SOURCE_FIELDS = frozenset(
    {
        "clause.voice",
        "clause.transitivity",
        "clause.tense",
        "clause.perfect",
        "clause.progressive",
        "clause.mood",
        "clause.polarity",
        "clause.kind",
        "argument.role",
        "argument.relation",
        "np.number",
        "np.pronoun.person",
        "np.pronoun.number",
        "np.pronoun.gender",
        "np.pronoun.case",
        "np.head.kind",
        "np.demonstrative",
        "np.modifiers",
        "np.possessor",
        "np.definiteness",
        "np.degree",
        "np.possessor.np",
        "np.post_modifiers",
        "np.coordinated",
    }
)

IR_FIELD_JUSTIFICATIONS = MappingProxyType(
    {
        "source_token.index": "Stable sentence-local token order supports generic ledger reporting.",
        "source_token.disposition": "The realization ledger accounts for every source token.",
        "source_token.disposition_reason": "The token ledger explains absorbed and dropped source material.",
        "modifier.kind": "Modifier kinds separate numeral, ordinal, and ordinary adjective handling.",
        "modifier.pos": "Coarse POS selects the source lexicon category.",
        "modifier.value": "A parsed numeral value determines its composed lexical sequence.",
        "modifier.literal": "Digit-containing tokens preserve their exact source spelling.",
        "modifier.sub_modifiers": "Adverbial modifiers remain attached to their modified word.",
        "possessor.np": "Possessors retain their full source NP structure.",
        "post_modifier.kind": "Post-modifier kinds distinguish PP and clause attachment.",
        "post_modifier.adposition": "The source adposition determines the lexical post-modifier word.",
        "post_modifier.np": "Post-modifier objects retain their full source NP structure.",
        "post_modifier.link": "Attached clauses preserve the source clause relation and marker.",
        "coordination.conj": "The source conjunction is preserved for realization.",
        "coordination.np": "Coordinated NPs retain the full second conjunct.",
        "clause_link.relation": "The parser relation selects generic clause-link order and marker behavior.",
        "clause_link.marker": "The source conjunction or subordinator is realized as a lexical word.",
        "clause_link.clause": "Each linked verbal head retains its own source-derived clause values.",
        "clause_link.source_tokens": "Linked clause tokens remain available for the source ledger.",
        "clause.links": "Embedded and coordinated clauses retain their source relations.",
        "sentence.source_tokens": "All sentence tokens remain available to the fallback ledger.",
        "sentence.numeral_spans": "Parser-detected CARDINAL spans let the rootless fallback compose numerals.",
        "source_token.text": "Source spelling is needed for literal and residual realization.",
        "source_token.lemma": "Source lemmas support lexical identity and residual realization.",
        "source_token.pos": "Parser POS selects the profile-owned lexical word shape.",
        "source_token.tag": "Fine POS tags retain observable source morphology.",
        "source_token.dep": "Dependency labels preserve generic argument and token structure.",
        "source_token.morph": "Parser morphology preserves observable English distinctions.",
        "source_token.head_index": "Head indices preserve generic dependency structure.",
        "np.literal": "Digit-containing NP heads preserve their exact source spelling.",
        "np.pos": "Coarse POS selects the source lexicon category.",
        "np.definiteness": "Article realization consumes parser-observed determiner morphology.",
        "np.numeral_value": "The parsed integer determines composed numeral identity.",
        "np.post_modifiers": "Structured PP and clause attachments preserve NP structure.",
        "np.head_indices": "Source token indices of the head words give output words their provenance.",
        "np.determiner_index": "The determiner token that fixed definiteness is the article's provenance.",
        "np.demonstrative_index": "The demonstrative token is the provenance of the demonstrative word.",
        "np.predeterminers": "Predeterminers (all, both, half) are closed-class words before the NP.",
        "np.adverbs": "NP-attached adverbs follow the noun phrase.",
        "clause.modals": "Modal auxiliaries are closed-class words before the verb.",
        "modifier.degree": "Comparative/superlative morphology of a modifier.",
        "modifier.indices": "Source token indices give modifier words their provenance.",
        "post_modifier.index": "The source adposition token is the provenance of the adposition word.",
        "argument.preposition_index": "The source preposition token is the provenance of its word.",
        "clause.predicate_index": "The predicate token is the provenance of the verb word.",
    }
)


@dataclass
class SourceToken:
    text: str
    lemma: str = ""
    pos: str = ""
    tag: str = ""
    dep: str = ""
    morph: dict[str, tuple[str, ...]] = field(default_factory=dict)
    head_index: int | None = None
    index: int | None = None
    disposition: TokenDisposition | None = None
    disposition_reason: str | None = None


class TokenDispositionLedger:
    def __init__(self, tokens: Iterable[SourceToken] = ()):
        self._states: dict[int, tuple[TokenDisposition | None, str | None]] = {}
        for token in tokens:
            if token.index is not None:
                self._states[token.index] = (token.disposition, token.disposition_reason)

    def get(self, index: int | None) -> tuple[TokenDisposition | None, str | None] | None:
        return None if index is None else self._states.get(index)

    def record(
        self, index: int | None, disposition: TokenDisposition, reason: str | None = None
    ) -> None:
        if index is not None:
            current = self._states.get(index)
            if current is None or current[0] is None:
                self._states[index] = (disposition, reason)

    def set_disposition(self, index: int | None, disposition: TokenDisposition) -> None:
        if index is not None:
            _, reason = self._states.get(index, (None, None))
            self._states[index] = (disposition, reason)

    def set_reason(self, index: int | None, reason: str | None) -> None:
        if index is not None:
            disposition, _ = self._states.get(index, (None, None))
            self._states[index] = (disposition, reason)

    def sync(self, tokens: Iterable[SourceToken]) -> None:
        for token in tokens:
            state = self.get(token.index)
            if state is not None:
                token.disposition, token.disposition_reason = state


@dataclass
class Modifier:
    text: str
    lemma: str
    kind: ModifierKind = "modifier"
    pos: str = ""
    value: int | None = None
    literal: bool = False
    sub_modifiers: list[Modifier] = field(default_factory=list)
    indices: tuple[int, ...] = ()
    degree: Degree = "none"


@dataclass
class Possessor:
    np: NounPhrase


@dataclass
class PostModifier:
    kind: PostModifierKind
    adposition: str | None = None
    np: NounPhrase | None = None
    link: ClauseLink | None = None
    index: int | None = None


@dataclass
class Coordination:
    conj: SourceToken | None
    np: NounPhrase


@dataclass
class ClauseLink:
    relation: ClauseLinkRelation
    marker: SourceToken | None
    clause: Clause
    source_tokens: list[SourceToken] = field(default_factory=list)


@dataclass
class NounPhrase:
    head: str
    kind: NounPhraseKind = "noun"
    number: Number = UNSPECIFIED
    demonstrative: Demonstrative = "none"
    person: str = UNSPECIFIED
    gender: str = UNSPECIFIED
    case: str = UNSPECIFIED
    modifiers: list[Modifier] = field(default_factory=list)
    possessor: Possessor | None = None
    post_modifiers: list[PostModifier] = field(default_factory=list)
    coordinated: list[Coordination] = field(default_factory=list)
    source_tokens: list[SourceToken] = field(default_factory=list)
    morphology: dict[str, tuple[str, ...]] = field(default_factory=dict)
    surface: str | None = None
    pos: str = "NOUN"
    definiteness: Definiteness = UNSPECIFIED
    numeral_value: int | None = None
    literal: bool = False
    head_indices: tuple[int, ...] = ()
    determiner_index: int | None = None
    demonstrative_index: int | None = None
    predeterminers: list[Modifier] = field(default_factory=list)
    adverbs: list[Modifier] = field(default_factory=list)
    degree: Degree = "none"


@dataclass
class Argument:
    relation: ArgumentRelation
    role: ArgumentRole
    np: NounPhrase
    source_dep: str = ""
    source_tokens: list[SourceToken] = field(default_factory=list)
    preposition: str | None = None
    preposition_index: int | None = None


@dataclass
class Clause:
    predicate: str = ""
    predicate_pos: str = ""
    kind: ClauseKind = "verbal"
    polarity: Polarity = "positive"
    tense: Tense = UNSPECIFIED
    perfect: bool = False
    progressive: bool = False
    mood: Mood = "declarative"
    transitivity: bool = False
    voice: Voice = "active"
    arguments: list[Argument] = field(default_factory=list)
    adverbs: list[Modifier] = field(default_factory=list)
    modifiers: list[Modifier] = field(default_factory=list)
    fragments: list[list[str]] = field(default_factory=list)
    source_tokens: list[SourceToken] = field(default_factory=list)
    argument_order: list[tuple[ArgumentRelation, str]] = field(default_factory=list)
    links: list[ClauseLink] = field(default_factory=list)
    predicate_index: int | None = None
    modals: list[Modifier] = field(default_factory=list)


@dataclass
class SentenceIR:
    clause: Clause
    source_text: str
    rules: list[str] = field(default_factory=list)
    fragments: list[list[str]] = field(default_factory=list)
    source_tokens: list[SourceToken] = field(default_factory=list)
    numeral_spans: list[tuple[int, int]] = field(default_factory=list)
