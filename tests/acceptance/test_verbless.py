"""Verbless input (bare NPs, numerals, interjections) is realized by the dialect's grammar."""

import copy
import itertools
from functools import lru_cache

import pytest

from conlang.core.base import Translator
from conlang.core.features import IncompatibleFeatures
from conlang.core.parser import parse
from conlang.core.registry import discover_languages

PROFILE = discover_languages()["austronesian"]

SINGLE_NP = (
    "the cat",
    "a cat",
    "the cats",
    "cats",
    "three dogs",
    "the three big dogs",
    "this small dog",
    "my cat",
    "the cat in the house",
    "one hundred and one dogs",
    "two hundred and fifty dogs",
    "one hundred dogs and one cat",
    "101 dogs",
)
LIST_INPUT = ("one cat, two cats, three cats", ("one cat", "two cats", "three cats"))
INTERJECTION = "Hello!"


def _valid_dialects():
    dialects = []
    articles = [("none", None)] + [
        (a, p) for a in ("both", "definite_only", "indefinite_only") for p in ("before", "after")
    ]
    modifiers = [("after", "none"), ("after", "particle"), ("before", None)]
    for (art, pos), number, (mod, linker), demo in itertools.product(
        articles,
        ("none", "particle", "full_reduplication", "partial_reduplication"),
        modifiers,
        ("unmarked", "two_way"),
    ):
        fixed = {
            "articles": art,
            "noun_number": number,
            "modifier_position": mod,
            "demonstratives": demo,
        }
        if pos:
            fixed["article_position"] = pos
        if linker:
            fixed["linker"] = linker
        dialects.append(fixed)
    return dialects


def _pairwise(candidates):
    """Greedy all-pairs selection: every option pair that occurs in some candidate is covered."""

    def pairs(candidate):
        return set(itertools.combinations(sorted(candidate.items()), 2))

    uncovered = set().union(*(pairs(c) for c in candidates))
    chosen = []
    while uncovered:
        best = max(candidates, key=lambda c: len(pairs(c) & uncovered))
        chosen.append(best)
        uncovered -= pairs(best)
    return chosen


MATRIX = _pairwise(_valid_dialects())


def _label(fixed):
    return "-".join(f"{key}={value}" for key, value in sorted(fixed.items()))


@lru_cache(maxsize=None)
def _parsed(text):
    return parse(text)


def fresh(text):
    return copy.deepcopy(_parsed(text))


def pairs(words):
    return [(word.surface(), word.gloss()) for word in words]


def morphemes(words):
    return [morpheme for word in words for morpheme in word.morphemes]


def glosses(words):
    return [morpheme.gloss for morpheme in morphemes(words)]


def root_gloss(word):
    return next((m.gloss for m in word.morphemes if m.kind == "root"), None)


def carrier_np(text):
    sentence = fresh(f"I saw {text}.")[0]
    return next(a.np for a in sentence.clause.arguments if a.relation == "object")


def expected_np(translator, text):
    words = translator.realizer._np_words(carrier_np(text), translator.lexicon, [])
    translator._surface_words(words)
    return pairs(words)


def translate_one(translator, text, check=False):
    results = translator.translate(text, check=check)
    assert len(results) == 1
    return results[0]


def check_parity(translator):
    for text in SINGLE_NP:
        result = translate_one(translator, text, check=True)
        assert pairs(result.words) == expected_np(translator, text), text
        assert "IR audit passed." in result.rules, (text, result.rules)
    text, items = LIST_INPUT
    result = translate_one(translator, text, check=True)
    expected = [pair for item in items for pair in expected_np(translator, item)]
    assert pairs(result.words) == expected
    assert "IR audit passed." in result.rules
    result = translate_one(translator, INTERJECTION, check=True)
    word = translator.realizer._lexical_word("hello", "INTJ", translator.lexicon)
    translator._surface_words([word])
    assert pairs(result.words) == pairs([word])
    assert "IR audit passed." in result.rules


def check_ledger(translator):
    for text in (*SINGLE_NP, LIST_INPUT[0], INTERJECTION):
        sentences = fresh(text)
        assert len(sentences) == 1
        assert sentences[0].clause.kind in {"nominal", "interjection"}, text
        translator.realizer.realize(sentences[0], translator.lexicon)
        assert all(t.disposition is not None for t in sentences[0].source_tokens), text


def check_articles(translator):
    system = translator.features["articles"]
    the = translate_one(translator, "the cat").words
    indefinite = translate_one(translator, "a cat").words
    for words in (the, indefinite):
        assert not {"THE", "A", "AN"} & set(glosses(words))
    allowed = {
        "none": set(),
        "definite_only": {"DEF"},
        "indefinite_only": {"INDEF"},
        "both": {"DEF", "INDEF"},
    }[system]
    for words in (the, indefinite):
        assert {"DEF", "INDEF"} & set(glosses(words)) <= allowed
    assert ("DEF" in glosses(the)) == (system in {"both", "definite_only"})
    assert ("INDEF" in glosses(indefinite)) == (system in {"both", "indefinite_only"})
    if system != "none":
        article = "DEF" if "DEF" in glosses(the) else "INDEF"
        source = the if article == "DEF" else indefinite
        position = 0 if translator.features["article_position"] == "before" else len(source) - 1
        assert source[position].gloss() == article
    lemmas = {e["lemma"] for e in translator.lexicon.export() if e["category"] == "lexical"}
    assert not {"the", "a", "an"} & lemmas


def check_number(translator):
    strategy = translator.features["noun_number"]
    singular = translate_one(translator, "the cat").words
    plural = translate_one(translator, "the cats").words
    if strategy == "none":
        assert pairs(plural) == pairs(singular)
        assert pairs(translate_one(translator, "cats").words) == pairs(
            translate_one(translator, "cat").words
        )
    elif strategy == "particle":
        assert "PL" in glosses(plural) and "PL" not in glosses(singular)
    else:
        assert "RED" in glosses(plural) and "RED" not in glosses(singular)
        head = next(w for w in plural if root_gloss(w) == "CAT")
        assert [m.kind for m in head.morphemes][0] == "reduplicant"
    big = translate_one(translator, "the three big dogs").words
    for word in big:
        if root_gloss(word) in {"THREE", "BIG"}:
            assert "RED" not in word.gloss()
    order = [root_gloss(w) for w in big if root_gloss(w)]
    if translator.features["modifier_position"] == "before":
        assert order.index("BIG") < order.index("DOG")
    else:
        assert order.index("DOG") < order.index("BIG")


def run_all(translator):
    check_parity(translator)
    check_ledger(translator)
    check_articles(translator)
    check_number(translator)


def test_matrix_covers_every_option_of_every_feature():
    seen: dict[str, set[str]] = {}
    for fixed in MATRIX:
        for key, value in fixed.items():
            seen.setdefault(key, set()).add(value)
    assert seen == {
        "articles": {"none", "both", "definite_only", "indefinite_only"},
        "article_position": {"before", "after"},
        "noun_number": {"none", "particle", "full_reduplication", "partial_reduplication"},
        "modifier_position": {"after", "before"},
        "linker": {"none", "particle"},
        "demonstratives": {"unmarked", "two_way"},
    }


@pytest.mark.parametrize("fixed", MATRIX, ids=_label)
def test_verbless_input_follows_the_dialect_in_the_matrix(fixed):
    try:
        translator = Translator(PROFILE, "7", fixed=fixed)
    except IncompatibleFeatures:
        pytest.skip("combination rejected by the catalog")
    run_all(translator)


@pytest.mark.parametrize("seed", range(50))
def test_verbless_input_follows_the_dialect_across_seeds(seed):
    run_all(Translator(PROFILE, str(seed)))


def test_same_seed_gives_identical_verbless_output():
    for text in (*SINGLE_NP, LIST_INPUT[0], INTERJECTION):
        first = pairs(translate_one(Translator(PROFILE, "11"), text).words)
        second = pairs(translate_one(Translator(PROFILE, "11"), text).words)
        assert first == second, text


def test_articles_never_mint_lexical_roots_in_the_lexicon_export():
    translator = Translator(PROFILE, "2026")
    translator.translate("the cat")
    translator.translate("a cat")
    assert not any(e["lemma"] in {"the", "a", "an"} for e in translator.lexicon.export())


def test_rootless_fallback_is_dialect_aware_for_determiners():
    for system in ("none", "both", "definite_only", "indefinite_only"):
        fixed = {"articles": system}
        if system != "none":
            fixed["article_position"] = "after"
        translator = Translator(PROFILE, "5", fixed=fixed)
        result = translate_one(translator, "The happy dog sleeps.")
        assert result.fallback_spans
        assert "THE" not in glosses(result.words)
        assert ("DEF" in glosses(result.words)) == (system in {"both", "definite_only"})


def test_punctuation_only_input_still_uses_the_rootless_fallback():
    result = translate_one(Translator(PROFILE, "5"), "!!!")
    assert result.words == [] and result.fallback_spans


NUMERALS = ("one hundred and one", "two hundred and fifty", "one thousand")


def check_numerals(translator):
    for text in NUMERALS:
        bare = translate_one(translator, text, check=True)
        assert pairs(bare.words) == expected_np(translator, text), text
        assert "IR audit passed." in bare.rules
        assert "AND" not in glosses(bare.words)
        with_noun = translate_one(translator, f"{text} dogs")
        assert "AND" not in glosses(with_noun.words)
        numeral = pairs(translator.realizer.numeral_sequence(_value(text), translator.lexicon))
        assert numeral == [p for p in pairs(with_noun.words) if p in numeral]
    coordinated = glosses(translate_one(translator, "one hundred dogs and one cat").words)
    assert coordinated.count("AND") == 1 and coordinated.count("ONE") == 1
    assert coordinated.index("HUNDRED") < coordinated.index("AND") < coordinated.index("CAT")
    literal = translate_one(translator, "101 dogs").words
    assert "101" in [w.surface() for w in literal if w.literal]


def _value(text):
    from conlang.core.parser import numeral_value

    return numeral_value([text])


@pytest.mark.parametrize("fixed", MATRIX, ids=_label)
def test_numerals_match_the_sentence_path_in_the_matrix(fixed):
    check_numerals(Translator(PROFILE, "7", fixed=fixed))


@pytest.mark.parametrize("seed", range(20))
def test_numerals_match_the_sentence_path_across_seeds(seed):
    check_numerals(Translator(PROFILE, str(seed)))


def test_numeral_conjunction_is_absorbed_by_the_parse_not_realized():
    for text in ("one hundred and one dogs", "two hundred and fifty dogs", "one hundred and one"):
        tokens = parse(text)[0].source_tokens
        conjunction = next(t for t in tokens if t.dep == "cc")
        assert (conjunction.disposition, conjunction.disposition_reason) == (
            "absorbed",
            "numeral conjunction",
        )
    tokens = parse("one hundred dogs and one cat")[0].source_tokens
    conjunction = next(t for t in tokens if t.dep == "cc")
    assert conjunction.disposition is None


def test_fallback_composes_cardinal_spans_and_absorbs_the_inner_and():
    translator = Translator(PROFILE, "2026")
    for text, value in (
        ("very quickly two hundred and fifty", 250),
        ("very quickly one hundred and one", 101),
    ):
        sentence = parse(text)[0]
        assert sentence.clause.kind == "rootless"
        result = translator._fallback_result(sentence.source_text, None, sentence)
        numeral = pairs(translator.realizer.numeral_sequence(value, translator.lexicon))
        assert pairs(result.words)[-len(numeral) :] == numeral
        assert "AND" not in glosses(result.words)
        conjunction = next(t for t in sentence.source_tokens if t.dep == "cc")
        assert conjunction.disposition_reason == "numeral conjunction"
        assert all(t.disposition is not None for t in sentence.source_tokens)
    result = translator._fallback_result("very quickly one hundred and one", RuntimeError("x"))
    assert glosses(result.words)[-2:] == ["HUNDRED", "ONE"]


def test_fallback_keeps_unparseable_spans_token_by_token():
    translator = Translator(PROFILE, "2026")
    sentence = parse("very quickly 101")[0]
    result = translator._fallback_result(sentence.source_text, None, sentence)
    assert [w.surface() for w in result.words][-1] == "101"
    assert result.words[-1].literal
