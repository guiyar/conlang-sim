"""Language-independent parsed English representation."""

from dataclasses import dataclass, field
from types import MappingProxyType

UNSPECIFIED = "UNSPECIFIED"
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
    morph: dict = field(default_factory=dict)
    head_index: int | None = None
    index: int | None = None
    disposition: str | None = None
    disposition_reason: str | None = None


@dataclass
class Modifier:
    text: str
    lemma: str
    kind: str = "modifier"
    pos: str = ""
    value: int | None = None
    literal: bool = False
    sub_modifiers: list = field(default_factory=list)
    indices: tuple = ()
    degree: str = "none"


@dataclass
class Possessor:
    np: "NounPhrase"


@dataclass
class PostModifier:
    kind: str
    adposition: str | None = None
    np: "NounPhrase | None" = None
    link: "ClauseLink | None" = None
    index: int | None = None


@dataclass
class Coordination:
    conj: SourceToken | None
    np: "NounPhrase"


@dataclass
class ClauseLink:
    relation: str
    marker: SourceToken | None
    clause: "Clause"
    source_tokens: list = field(default_factory=list)


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
    pos: str = "NOUN"
    definiteness: str = UNSPECIFIED
    numeral_value: int | None = None
    literal: bool = False
    head_indices: tuple = ()
    determiner_index: int | None = None
    demonstrative_index: int | None = None
    predeterminers: list = field(default_factory=list)
    adverbs: list = field(default_factory=list)
    degree: str = "none"


@dataclass
class Argument:
    relation: str
    role: str
    np: NounPhrase
    source_dep: str = ""
    source_tokens: list = field(default_factory=list)
    preposition: str | None = None
    preposition_index: int | None = None


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
    links: list = field(default_factory=list)
    predicate_index: int | None = None
    modals: list = field(default_factory=list)


@dataclass
class SentenceIR:
    clause: Clause
    source_text: str
    rules: list = field(default_factory=list)
    fragments: list = field(default_factory=list)
    source_tokens: list = field(default_factory=list)
    numeral_spans: list = field(default_factory=list)
