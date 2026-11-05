"""Invariants over the probe sentences, the dialect matrix, and a seed sweep."""

import random
import re

import pytest
from probes import (
    MATRIX,
    PROBES,
    PROFILE,
    dialect_translators,
    fresh,
    glosses,
    make_translator,
    morphemes,
)

from conlang.core.base import Translator
from conlang.core.results import is_info

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


def _realize(translator, sentence):
    if sentence.clause.kind == "rootless":
        result = translator._fallback_result(sentence.source_text, None, sentence)
        return result.words, result.rules
    return translator.realizer.realize(sentence, translator.lexicon)


@pytest.mark.parametrize("name,translator", ALL, ids=IDS)
def test_ledger_dispositions_are_backed_by_output_words(name, translator):
    for text in PROBES:
        for sentence in fresh(text):
            words, _ = _realize(translator, sentence)
            emitted = {i for word in words for i in word.sources}
            for token in sentence.source_tokens:
                where = (name, text, token.text)
                assert token.disposition in {"realized", "absorbed", "dropped"}, where
                if token.disposition == "realized":
                    assert token.index in emitted, where
                else:
                    assert token.disposition_reason, where


@pytest.mark.parametrize("name,translator", ALL, ids=IDS)
def test_predeterminers_and_np_adverbs_are_realized_not_residual(name, translator):
    for text, word in (("All the dogs ate.", "All"), ("Why is the cat here?", "here")):
        sentence = fresh(text)[0]
        words, rules = _realize(translator, sentence)
        token = next(t for t in sentence.source_tokens if t.text == word)
        assert token.disposition == "realized"
        assert token.index in {i for w in words for i in w.sources}
        assert f"residual token: {word}" not in rules


AMBIGUOUS = (
    "The dog that the cat saw is big.",
    "I think that he left.",
    "That dog is big.",
    "I want to eat.",
    "I went to the house.",
    "No, I did not.",
    "She has no dog.",
    "What is that?",
    "Which dog ate?",
    "Whose dog is it?",
    "When did the cat eat?",
)


@pytest.mark.parametrize("seed", ["0", "2026", "5"])
def test_function_words_have_one_form_per_identity_and_distinct_glosses(seed):
    translator = Translator(PROFILE, seed, fixed={"demonstratives": "unmarked"})
    for text in AMBIGUOUS:
        translator.translate(text)
    function = [
        e for e in translator.lexicon.export() if e["category"] == "function" and e["lemma"]
    ]
    forms_by_gloss: dict[str, set[str]] = {}
    for entry in function:
        forms_by_gloss.setdefault(entry["gloss"], set()).add(entry["form"])
    assert all(len(forms) == 1 for forms in forms_by_gloss.values()), forms_by_gloss
    glosses_for = {e["lemma"]: set() for e in function}
    for entry in function:
        glosses_for[entry["lemma"]].add(entry["gloss"])
    assert {"THAT.DEM", "THAT.COMP", "THAT.REL"} <= glosses_for["that"]
    assert {"TO", "TO.INF"} <= glosses_for["to"]
    assert {"NO", "NO.INTJ"} <= glosses_for["no"]


def test_same_lemma_and_pos_always_yield_the_same_form():
    translator = Translator(PROFILE, "2026")
    for lemma, pos in (("that", "DET"), ("that", "PRON"), ("to", "PART"), ("to", "ADP")):
        assert translator.lexicon.root(lemma, pos) == translator.lexicon.root(lemma, pos)
    forms = {translator.lexicon.root("that", pos) for pos in ("DET", "SCONJ", "PRON")}
    assert len(forms) == 3
    assert translator.lexicon.root("what", "PRON") == translator.lexicon.root("what", "DET")
    assert translator.lexicon.root("why", "SCONJ") == translator.lexicon.root("why", "ADV")


ROLE_DIALECTS = [
    {
        "alignment": alignment,
        "clause_order": order,
        "case_particles": case,
        "pronoun_strategy": strategy,
    }
    for alignment, case in (
        ("symmetrical_voice", "preposed"),
        ("active_passive", "none"),
        ("active_passive", "preposed"),
        ("ergative", "preposed"),
        ("plain", "none"),
    )
    for order in ("VSO", "VOS", "SVO", "SOV")
    for strategy in ("free", "clitic_verb", "clitic_second")
]


def _label(fixed):
    return "-".join(fixed.values())


@pytest.mark.parametrize("fixed", ROLE_DIALECTS, ids=_label)
def test_dropped_subject_clauses_keep_the_patient_a_patient(fixed):
    translator = make_translator(fixed)
    for text in ("Eat the dog!", "Don't eat the dog!", "Thank you."):
        words = translator.translate(text)[0].words
        tags = [m.gloss for m in morphemes(words)]
        where = (fixed, text, tags)
        if fixed["alignment"] == "symmetrical_voice":
            assert "PF" in tags and "AF" not in tags, where
        elif fixed["alignment"] == "active_passive":
            assert "PASS" in tags and "AF" not in tags, where
        elif fixed["clause_order"] in {"SVO", "VOS"}:
            if "dog" in text:
                verb = next(i for i, w in enumerate(words) if "EAT" in w.gloss())
                dog = next(i for i, w in enumerate(words) if w.gloss() == "DOG")
                assert dog > verb, where
        elif "dog" in text:
            assert "P2" in tags, where
        else:
            assert any(t.startswith("P3") for t in tags) and "P2" in tags, where


def test_imperative_without_marking_notes_it_at_info_level():
    result = make_translator(ROLE_DIALECTS[0]).translate("Eat the dog!")[0]
    assert any(is_info(rule) and "imperative" in rule for rule in result.rules)


@pytest.mark.parametrize("name,translator", ALL, ids=IDS)
def test_dative_shift_and_prepositional_recipients_are_marked_alike(name, translator):
    shifted = translator.translate("She gave me the dog.")[0].words
    prepositional = translator.translate("She gave the dog to me.")[0].words
    assert sorted(glosses(shifted)) == sorted(glosses(prepositional)), name

    def marker(words):
        recipient = next(i for i, w in enumerate(words) if w.morphemes[0].gloss in {"P1", "P1SG"})
        return words[recipient - 1].morphemes[0].gloss

    assert marker(shifted) == marker(prepositional), name
    assert marker(shifted) in {"TO", "OBL"}, name


TAM_TAGS = {"PAST", "PRESENT", "FUTURE", "NONPAST", "CONT", "PERF", "IMPF"}


def _tags(translator, text):
    return [m.gloss for m in morphemes(translator.translate(text)[0].words)]


@pytest.mark.parametrize("name,translator", ALL, ids=IDS)
def test_perfect_modals_degree_and_infinitives(name, translator):
    perfect = _tags(translator, "The cat has eaten the dog.")
    plain = _tags(translator, "The cat eats the dog.")
    assert perfect != plain, name
    if translator.features["tam_system"] == "aspect3":
        assert "PERF" in perfect, name
    else:
        assert "PAST" in perfect, name
    assert "CAN" in _tags(translator, "The cat can eat the dog."), name
    assert "COMP" in _tags(translator, "This dog is bigger than that cat."), name
    assert "SUP" in _tags(translator, "The cat is the biggest."), name
    infinitive = _tags(translator, "I want to eat.")
    assert len([t for t in infinitive if t in TAM_TAGS]) == 1, (name, infinitive)


@pytest.mark.parametrize("name,translator", ALL, ids=IDS)
def test_adverb_modifiers_follow_modifier_position_and_linker(name, translator):
    result = translator.translate("The cat very quickly ate the dog.")[0]
    assert not any("residual" in rule for rule in result.rules), name
    tags = [m.gloss for m in morphemes(result.words)]
    quickly, very = tags.index("QUICKLY"), tags.index("VERY")
    if translator.features["modifier_position"] == "before":
        assert very + 1 == quickly, (name, tags)
    else:
        gap = 2 if translator.features["linker"] == "particle" else 1
        assert very - quickly == gap, (name, tags)
