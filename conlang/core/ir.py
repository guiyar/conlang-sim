"""Language-independent parsed English representation."""

from dataclasses import dataclass, field

UNSPECIFIED = "UNSPECIFIED"
STRUCTURAL_FIELDS = frozenset({"clause.predicate", "clause.predicate_pos", "clause.arguments", "clause.argument_order", "clause.kind", "clause.fragments", "clause.adverbs", "argument.preposition", "np.head", "np.surface", "rules"})
VALID_SOURCE_FIELDS = frozenset({
    "clause.voice", "clause.transitivity", "clause.tense", "clause.perfect", "clause.progressive",
    "clause.mood", "clause.polarity", "clause.kind", "argument.role", "argument.relation",
    "np.number", "np.pronoun.person", "np.pronoun.number", "np.pronoun.gender", "np.pronoun.case",
    "np.head.kind", "np.demonstrative", "np.modifiers", "np.possessor",
})


@dataclass
class SourceToken:
    text: str
    lemma: str = ""
    pos: str = ""
    tag: str = ""
    dep: str = ""
    morph: dict = field(default_factory=dict)
    head_index: int | None = None


@dataclass
class Modifier:
    text: str
    lemma: str
    kind: str = "modifier"


@dataclass
class NounPhrase:
    head: str
    kind: str = "noun"
    number: str = UNSPECIFIED
    demonstrative: str = "none"
    person: str = UNSPECIFIED
    gender: str = UNSPECIFIED
    case: str = UNSPECIFIED
    modifiers: list = field(default_factory=list)
    possessor: object = None
    post_modifiers: list = field(default_factory=list)
    coordinated: list = field(default_factory=list)
    source_tokens: list = field(default_factory=list)
    morphology: dict = field(default_factory=dict)
    surface: str | None = None


@dataclass
class Argument:
    relation: str
    role: str
    np: NounPhrase
    source_dep: str = ""
    source_tokens: list = field(default_factory=list)
    preposition: str | None = None


@dataclass
class Clause:
    predicate: str = ""
    predicate_pos: str = ""
    kind: str = "verbal"
    polarity: str = "positive"
    tense: str = UNSPECIFIED
    perfect: bool = False
    progressive: bool = False
    mood: str = "declarative"
    transitivity: bool = False
    voice: str = "active"
    arguments: list = field(default_factory=list)
    adverbs: list = field(default_factory=list)
    modifiers: list = field(default_factory=list)
    fragments: list = field(default_factory=list)
    source_tokens: list = field(default_factory=list)
    argument_order: list = field(default_factory=list)


@dataclass
class SentenceIR:
    clause: Clause
    source_text: str
    rules: list = field(default_factory=list)
    fragments: list = field(default_factory=list)