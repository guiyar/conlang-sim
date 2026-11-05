"""spaCy boundary: parse English and immediately convert to language-neutral IR."""

from .ir import (
    Clause,
    SentenceIR,
)
from .ir_validation import validate_sentence_ir
from .parsing.clause_builder import ClauseBuilder
from .parsing.context import ParseContext
from .parsing.english import EnglishParser
from .parsing.numeral import numeral_value
from .parsing.token_ledger import TokenLedger
from .results import info

__all__ = [
    "MODEL_NAME",
    "MODEL_VERSION",
    "fallback_source",
    "numeral_value",
    "parse",
    "parser_versions",
]

MODEL_NAME = EnglishParser.MODEL_NAME
MODEL_VERSION = EnglishParser.MODEL_VERSION
_model = EnglishParser.model
_is_all_caps = EnglishParser.is_all_caps
_analyze = EnglishParser.analyze
_original = EnglishParser.original
_span_text = EnglishParser.span_text


def parser_versions():
    return EnglishParser.versions()


def fallback_source(text):
    """Source tokens and CARDINAL spans for text that never reached the sentence parser."""
    doc = _analyze(text)
    ledger = TokenLedger(doc)
    return list(ledger.source.values()), ledger.numeral_spans


def parse(text):
    """Return one SentenceIR per sentence, preserving linked verbal heads."""
    if not text or not text.strip():
        return []
    doc = _analyze(text)
    sentences = []
    for sent in doc.sents:
        context = ParseContext.from_sentence(sent)
        builder = ClauseBuilder(context)
        source = context.source
        main_root = sent.root
        clause_heads = context.clause_heads
        numeral_spans = context.numeral_spans
        root_fallback = False
        if main_root not in clause_heads and clause_heads:
            main_root = min(clause_heads, key=lambda token: (token.i, token.dep_ == "relcl"))
            root_fallback = True
        if main_root not in clause_heads:
            fragment_clause = builder.build_fragment(main_root)
            if fragment_clause is not None:
                sentences.append(
                    SentenceIR(
                        fragment_clause,
                        _span_text(sent),
                        [],
                        [],
                        list(source.values()),
                        numeral_spans,
                    )
                )
                continue
            fragment = [[_original(token) for token in sent]]
            clause = Clause(
                kind="rootless", fragments=fragment, source_tokens=list(source.values())
            )
            sentences.append(
                SentenceIR(
                    clause,
                    _span_text(sent),
                    ["No verbal or be root found; source tokens use conlang lexical fallback."],
                    fragment,
                    list(source.values()),
                    numeral_spans,
                )
            )
            continue
        clause = builder.build_clause(main_root, not root_fallback)
        rules = []
        if root_fallback:
            rules.append(
                "The parser root was non-verbal; the available verbal head was realized and remaining tokens retained."
            )
        if any(token.dep_ in {"relcl", "acl", "ccomp", "xcomp", "advcl", "conj"} for token in sent):
            rules.append(
                info(
                    "Embedded and coordinated clauses use profile grammar; relative-clause gaps are simplified."
                )
            )
        sentences.append(
            SentenceIR(clause, _span_text(sent), rules, [], list(source.values()), numeral_spans)
        )
    return [validate_sentence_ir(sentence) for sentence in sentences]
