import pytest

from conlang.core.base import Translator
from conlang.core.parser import parse
from conlang.core.registry import discover_languages

PROFILE = discover_languages()["austronesian"]
SENTENCES = ("there is a cat", "There are three dogs.", "Is there a cat?", "There will be a cat.")


@pytest.mark.parametrize("text", SENTENCES)
def test_expletive_there_marks_an_existential_clause(text):
    sentence = parse(text)[0]
    assert sentence.clause.kind == "existential"
    expletive = next(t for t in sentence.source_tokens if t.dep == "expl")
    translator = Translator(PROFILE, "2026")
    translator.realizer.realize(sentence, translator.lexicon)
    assert (expletive.disposition, expletive.disposition_reason) == ("absorbed", "expletive")
    assert all(t.disposition is not None for t in sentence.source_tokens)


@pytest.mark.parametrize("seed", range(20))
def test_existential_has_no_residual_there_or_copula(seed):
    translator = Translator(PROFILE, str(seed))
    for text in SENTENCES:
        result = translator.translate(text, check=True)[0]
        glosses = [m.gloss for word in result.words for m in word.morphemes]
        assert "THERE" not in glosses and "BE" not in glosses, (text, glosses)
        assert not any("residual token" in rule for rule in result.rules)
        assert "IR audit passed." in result.rules


def test_existential_realizes_its_noun_phrase_as_in_a_bare_noun_phrase():
    translator = Translator(PROFILE, "2026")
    existential = [w.surface() for w in translator.translate("there is a cat")[0].words]
    bare = [w.surface() for w in translator.translate("a cat")[0].words]
    assert any(
        existential[i : i + len(bare)] == bare for i in range(len(existential) - len(bare) + 1)
    )


def test_there_as_a_locative_adverb_is_not_an_existential():
    sentence = parse("The cat sleeps there.")[0]
    assert sentence.clause.kind == "verbal"
