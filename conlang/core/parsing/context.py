"""Small sentence-scoped set of shared parser inputs."""

from dataclasses import dataclass
from typing import Any

from .grammar import GrammarAnalyzer
from .token_ledger import TokenLedger


@dataclass(frozen=True)
class ParseContext:
    sent: Any
    ledger: TokenLedger
    clause_heads: frozenset

    @classmethod
    def from_sentence(cls, sent):
        return cls(
            sent,
            TokenLedger(sent),
            frozenset(token for token in sent if GrammarAnalyzer.is_clause_head(token)),
        )

    @property
    def source(self):
        return self.ledger.source

    @property
    def numeral_spans(self):
        return self.ledger.numeral_spans

    def source_for(self, token):
        return self.ledger.source_for(token)
