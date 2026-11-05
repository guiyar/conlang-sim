"""Runtime validation for parsed, language-neutral sentence IR."""

from typing import get_args

from .ir import (
    ArgumentRelation,
    ArgumentRole,
    Clause,
    ClauseKind,
    ClauseLinkRelation,
    Definiteness,
    Degree,
    Demonstrative,
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
