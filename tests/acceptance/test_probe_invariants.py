"""Invariants over the probe sentences, the dialect matrix, and a seed sweep."""

import random
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


def _form_map(translator):
    lexicon = translator.lexicon
    return {**lexicon.entries, **lexicon.closed_forms}


@pytest.mark.parametrize("seed", ["2026", "0", "1", "13"])
def test_forms_do_not_depend_on_translation_order(seed):
    sentences = [*PROBES, "green apples", "a cat", "an apple", "Oh, thanks!", "He sat inside."]
    reference = None
    for shuffle in range(5):
        order = list(sentences)
        random.Random(shuffle).shuffle(order)
        translator = Translator(PROFILE, seed)
        for text in order:
            translator.translate(text)
        forms = _form_map(translator)
        export = translator.lexicon.export()
        if reference is None:
            reference = (forms, export)
        assert forms == reference[0], (seed, shuffle)
        assert export == reference[1], (seed, shuffle)


def test_green_apples_is_the_same_before_and_after_translating_a_cat():
    cold = Translator(PROFILE, "2026").translate("green apples")[0].words
    warm = Translator(PROFILE, "2026")
    warm.translate("a cat")
    assert [w.surface() for w in warm.translate("green apples")[0].words] == [
        w.surface() for w in cold
    ]
