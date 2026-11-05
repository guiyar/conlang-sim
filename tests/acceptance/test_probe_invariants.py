"""Invariants over the probe sentences, the dialect matrix, and a seed sweep."""

import re

import pytest
from probes import MATRIX, PROBES, PROFILE, dialect_translators, make_translator

from conlang.core.base import Translator

DIALECTS = list(dialect_translators())
SEEDS = [(f"seed{n}", Translator(PROFILE, str(n))) for n in range(50)]
ALL = DIALECTS + SEEDS
IDS = [name for name, _ in ALL]


def results_for(translator, text, check=False):
    return translator.translate(text, check=check)


@pytest.mark.parametrize("name,translator", ALL, ids=IDS)
def test_no_probe_crashes(name, translator):
    for text in PROBES:
        for result in results_for(translator, text):
            assert "Unexpected" not in " ".join(result.rules), (name, text, result.rules)


NUMERIC = re.compile(r"\d[\d,.:]*")


@pytest.mark.parametrize("name,translator", ALL, ids=IDS)
def test_numeric_tokens_are_preserved_once(name, translator):
    for text in (
        "I was born in 2026.",
        "It costs $5.",
        "The cat ate at 3:30.",
        "I saw 2 cats and 1,000 dogs.",
    ):
        expected = [m.rstrip(".,") for m in NUMERIC.findall(text)]
        words = [w for r in results_for(translator, text) for w in r.words]
        got = [NUMERIC.search(w.surface()).group().rstrip(".,") for w in words if w.literal]
        assert got == expected, (name, text, [w.surface() for w in words])


def test_currency_symbol_stays_attached_to_the_number():
    translator = make_translator(MATRIX[0])
    surfaces = [w.surface() for w in translator.translate("It costs $5.")[0].words]
    assert "$5" in surfaces


@pytest.mark.parametrize("name,translator", ALL, ids=IDS)
def test_check_passes_for_every_probe(name, translator):
    for text in PROBES:
        for result in results_for(translator, text, check=True):
            assert "IR audit passed." in result.rules, (name, text, result.rules)
