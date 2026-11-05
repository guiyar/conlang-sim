"""Sentence-local source token provenance and numeral token disposition."""

from ..ir import SourceToken
from .english import EnglishParser
from .numeral import numeral_value


class TokenLedger:
    def __init__(self, source):
        self.document = source
        self.doc = getattr(source, "doc", source)
        self.source = {token.i: self._source_token(token) for token in source}
        self.numeral_spans = [
            (entity.start, entity.end) for entity in source.ents if entity.label_ == "CARDINAL"
        ]
        self._absorb_numeral_conjunctions()

    @staticmethod
    def _source_token(token):
        return SourceToken(
            EnglishParser.original(token),
            token.lemma_,
            token.pos_,
            token.tag_,
            token.dep_,
            EnglishParser.morphology(token),
            token.head.i,
            token.i,
        )

    def source_for(self, token):
        return self.source.get(token.i)

    def _absorb_numeral_conjunctions(self):
        for start, end in self.numeral_spans:
            span = self.doc[start:end]
            if numeral_value(token.text for token in span) is None:
                continue
            for token in span:
                if token.dep_ != "cc" or token.head.pos_ != "NUM" or token.i + 1 >= end:
                    continue
                if self.doc[token.i + 1].pos_ == "NUM":
                    source = self.source[token.i]
                    source.disposition = "absorbed"
                    source.disposition_reason = "numeral conjunction"
