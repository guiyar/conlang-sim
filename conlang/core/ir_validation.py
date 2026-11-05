"""Runtime validation for parsed, language-neutral sentence IR."""

from types import MappingProxyType
from typing import get_args

from .final_ir import (
    FinalArgument,
    FinalClause,
    FinalClauseLink,
    FinalCoordination,
    FinalizedSentenceIR,
    FinalModifier,
    FinalNote,
    FinalNounPhrase,
    FinalPossessor,
    FinalPostModifier,
    FinalSourceToken,
)
from .ir import (
    ArgumentRelation,
    ArgumentRole,
    Clause,
    ClauseKind,
    ClauseLinkRelation,
    Definiteness,
    Degree,
    Demonstrative,
    Modifier,
    ModifierKind,
    Mood,
    NounPhrase,
    NounPhraseKind,
    Number,
    Polarity,
    PostModifierKind,
    SentenceIR,
    SourceToken,
    Tense,
    TokenDisposition,
    Voice,
)


class IRValidationError(ValueError):
    pass


def _validate_category(value, category, path):
    if value not in get_args(category):
        raise IRValidationError(f"invalid {path}: {value!r}")


def _validate_source_token(token: SourceToken):
    if token.disposition is not None:
        _validate_category(token.disposition, TokenDisposition, "source token disposition")
    if token.disposition is None and token.disposition_reason is not None:
        raise IRValidationError("source token disposition reason without a disposition")


def _validate_modifier(modifier, seen):
    _validate_category(modifier.kind, ModifierKind, "modifier kind")
    _validate_category(modifier.degree, Degree, "modifier degree")
    for nested in modifier.sub_modifiers:
        _validate_modifier(nested, seen)


def _validate_np(np: NounPhrase, seen_nps, seen_clauses):
    if id(np) in seen_nps:
        return
    seen_nps.add(id(np))
    _validate_category(np.kind, NounPhraseKind, "noun phrase kind")
    _validate_category(np.number, Number, "noun phrase number")
    _validate_category(np.demonstrative, Demonstrative, "demonstrative")
    _validate_category(np.definiteness, Definiteness, "definiteness")
    _validate_category(np.degree, Degree, "noun phrase degree")
    for modifier in (*np.modifiers, *np.predeterminers, *np.adverbs):
        _validate_modifier(modifier, seen_nps)
    if np.possessor is not None:
        _validate_np(np.possessor.np, seen_nps, seen_clauses)
    for post_modifier in np.post_modifiers:
        _validate_category(post_modifier.kind, PostModifierKind, "post-modifier kind")
        if post_modifier.np is not None:
            _validate_np(post_modifier.np, seen_nps, seen_clauses)
        if post_modifier.link is not None:
            _validate_clause(post_modifier.link.clause, seen_nps, seen_clauses)
    for coordination in np.coordinated:
        _validate_np(coordination.np, seen_nps, seen_clauses)


def _validate_clause(clause: Clause, seen_nps, seen_clauses):
    if id(clause) in seen_clauses:
        return
    seen_clauses.add(id(clause))
    _validate_category(clause.kind, ClauseKind, "clause kind")
    _validate_category(clause.polarity, Polarity, "clause polarity")
    _validate_category(clause.tense, Tense, "clause tense")
    _validate_category(clause.mood, Mood, "clause mood")
    _validate_category(clause.voice, Voice, "clause voice")
    for argument in clause.arguments:
        _validate_category(argument.relation, ArgumentRelation, "argument relation")
        _validate_category(argument.role, ArgumentRole, "argument role")
        _validate_np(argument.np, seen_nps, seen_clauses)
    for modifier in (*clause.adverbs, *clause.modifiers, *clause.modals):
        _validate_modifier(modifier, seen_nps)
    for link in clause.links:
        _validate_category(link.relation, ClauseLinkRelation, "clause link relation")
        _validate_clause(link.clause, seen_nps, seen_clauses)


def validate_sentence_ir(sentence: SentenceIR) -> SentenceIR:
    if not isinstance(sentence, SentenceIR):
        raise IRValidationError("expected SentenceIR")
    seen_indices = set()
    for token in sentence.source_tokens:
        _validate_source_token(token)
        if token.index is not None:
            if token.index in seen_indices:
                raise IRValidationError(f"duplicate source token index: {token.index}")
            seen_indices.add(token.index)
    for start, end in sentence.numeral_spans:
        if start < 0 or start >= end:
            raise IRValidationError(f"invalid numeral span: {(start, end)!r}")
        if seen_indices and (start < min(seen_indices) or end > max(seen_indices) + 1):
            raise IRValidationError(f"numeral span outside sentence tokens: {(start, end)!r}")
    _validate_clause(sentence.clause, set(), set())
    return sentence


def _final_source_token(token: SourceToken) -> FinalSourceToken:
    return FinalSourceToken(
        token.text,
        token.lemma,
        token.pos,
        token.tag,
        token.dep,
        MappingProxyType(dict(token.morph)),
        token.head_index,
        token.index,
        token.disposition,
        token.disposition_reason,
    )


def _final_modifier(modifier: Modifier) -> FinalModifier:
    return FinalModifier(
        modifier.text,
        modifier.lemma,
        modifier.kind,
        modifier.pos,
        modifier.value,
        modifier.literal,
        tuple(_final_modifier(item) for item in modifier.sub_modifiers),
        tuple(modifier.indices),
        modifier.degree,
    )


def _final_np(np: NounPhrase) -> FinalNounPhrase:
    return FinalNounPhrase(
        np.head,
        np.kind,
        np.number,
        np.demonstrative,
        np.person,
        np.gender,
        np.case,
        tuple(_final_modifier(item) for item in np.modifiers),
        None if np.possessor is None else FinalPossessor(_final_np(np.possessor.np)),
        tuple(
            FinalPostModifier(
                item.kind,
                item.adposition,
                None if item.np is None else _final_np(item.np),
                None if item.link is None else _final_clause_link(item.link),
                item.index,
            )
            for item in np.post_modifiers
        ),
        tuple(
            FinalCoordination(
                None if item.conj is None else _final_source_token(item.conj),
                _final_np(item.np),
            )
            for item in np.coordinated
        ),
        tuple(_final_source_token(item) for item in np.source_tokens),
        MappingProxyType(dict(np.morphology)),
        np.surface,
        np.pos,
        np.definiteness,
        np.numeral_value,
        np.literal,
        tuple(np.head_indices),
        np.determiner_index,
        np.demonstrative_index,
        tuple(_final_modifier(item) for item in np.predeterminers),
        tuple(_final_modifier(item) for item in np.adverbs),
        np.degree,
    )


def _final_clause_link(link) -> FinalClauseLink:
    return FinalClauseLink(
        link.relation,
        None if link.marker is None else _final_source_token(link.marker),
        _final_clause(link.clause),
        tuple(_final_source_token(item) for item in link.source_tokens),
    )


def _final_clause(clause: Clause) -> FinalClause:
    return FinalClause(
        clause.predicate,
        clause.predicate_pos,
        clause.kind,
        clause.polarity,
        clause.tense,
        clause.perfect,
        clause.progressive,
        clause.mood,
        clause.transitivity,
        clause.voice,
        tuple(
            FinalArgument(
                argument.relation,
                argument.role,
                _final_np(argument.np),
                argument.source_dep,
                tuple(_final_source_token(item) for item in argument.source_tokens),
                argument.preposition,
                argument.preposition_index,
            )
            for argument in clause.arguments
        ),
        tuple(_final_modifier(item) for item in clause.adverbs),
        tuple(_final_modifier(item) for item in clause.modifiers),
        tuple(tuple(fragment) for fragment in clause.fragments),
        tuple(_final_source_token(item) for item in clause.source_tokens),
        tuple(clause.argument_order),
        tuple(_final_clause_link(item) for item in clause.links),
        clause.predicate_index,
        tuple(_final_modifier(item) for item in clause.modals),
    )


def finalize_sentence_ir(sentence: SentenceIR) -> FinalizedSentenceIR:
    validate_sentence_ir(sentence)
    return FinalizedSentenceIR(
        _final_clause(sentence.clause),
        sentence.source_text,
        tuple(FinalNote(str(rule), getattr(rule, "level", "notice")) for rule in sentence.rules),
        tuple(tuple(fragment) for fragment in sentence.fragments),
        tuple(_final_source_token(item) for item in sentence.source_tokens),
        tuple(sentence.numeral_spans),
    )
