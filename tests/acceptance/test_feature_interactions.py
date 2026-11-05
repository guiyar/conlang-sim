"""Feature interactions: pairwise dialect matrix plus named multi-feature configurations."""

import pytest
from probes import MATRIX, PROFILE, label, make_translator

from conlang.core.base import Translator
from conlang.core.features import IncompatibleFeatures
from conlang.core.ir import Argument, Clause, Modifier, NounPhrase, Possessor, SentenceIR


def realize(translator, clause):
    words, rules = translator.realizer.realize(SentenceIR(clause, "test"), translator.lexicon)
    phonology = translator.phonology
    for word in words:
        word.realize(phonology.validate_surface, phonology.epenthetic_vowel)
    return words, rules


def rich_clauses():
    subject = NounPhrase(
        "dog",
        number="plural",
        definiteness="definite",
        modifiers=[Modifier("big", "big", pos="ADJ")],
        possessor=Possessor(NounPhrase("child", number="singular")),
    )
    pronoun = NounPhrase("I", kind="pronoun", person="1", number="singular")
    bird = NounPhrase("bird", number="plural", definiteness="indefinite")
    return {
        "progressive": Clause(
            predicate="see",
            predicate_pos="VERB",
            transitivity=True,
            progressive=True,
            arguments=[Argument("subject", "agent", subject), Argument("object", "patient", bird)],
        ),
        "negative_question": Clause(
            predicate="see",
            predicate_pos="VERB",
            transitivity=True,
            tense="past",
            polarity="negative",
            mood="interrogative",
            arguments=[Argument("subject", "agent", pronoun), Argument("object", "patient", bird)],
        ),
        "agentless_patient": Clause(
            predicate="see",
            predicate_pos="VERB",
            transitivity=True,
            tense="future",
            arguments=[Argument("object", "patient", bird)],
        ),
    }


CLAUSES = rich_clauses()


def accepted_dialects():
    dialects = []
    for index, fixed in enumerate(MATRIX):
        try:
            make_translator(fixed)
        except IncompatibleFeatures:
            continue
        dialects.append(pytest.param(fixed, id=f"m{index}"))
    return dialects


DIALECTS = accepted_dialects()


@pytest.mark.parametrize("clause_name", CLAUSES)
@pytest.mark.parametrize("fixed", DIALECTS)
def test_matrix_dialects_realize_valid_consistent_words(fixed, clause_name):
    translator = make_translator(fixed)
    words, rules = realize(translator, CLAUSES[clause_name])
    assert "Unexpected" not in " ".join(rules), label(fixed)
    phonology = translator.phonology
    for word in words:
        surface = word.surface()
        # Clitic dialects are excluded: see test_clitic_pronouns_keep_words_phonotactically_valid.
        if not word.literal and fixed["pronoun_strategy"] == "free":
            assert phonology.valid(phonology.segments(surface)), (label(fixed), surface)
        assert len(word.segmented().split("-")) == len(word.gloss().split("-")), label(fixed)


@pytest.mark.parametrize("fixed", DIALECTS)
def test_matrix_dialect_voice_and_tam_markers_match_their_positions(fixed):
    translator = make_translator(fixed)
    words, _ = realize(translator, CLAUSES["progressive"])
    morphemes = {m.gloss: m for w in words for m in w.morphemes}
    features = translator.features
    if features["voice_affix_position"] is not None:
        assert morphemes["AF"].kind == features["voice_affix_position"]
    if features["tam_affix_position"] is not None:
        tam = {"tense3": "PRESENT", "past_nonpast": "NONPAST", "aspect3": "IMPF"}[
            fixed["tam_system"]
        ]
        assert morphemes[tam].kind == features["tam_affix_position"]


@pytest.mark.xfail(strict=True, reason="vowel-only clitic after a vowel-final host leaves hiatus")
def test_clitic_pronouns_keep_words_phonotactically_valid():
    translator = make_translator(MATRIX[1])
    words, _ = realize(translator, CLAUSES["negative_question"])
    phonology = translator.phonology
    assert all(phonology.valid(phonology.segments(w.surface())) for w in words if not w.literal)


def verb_word(translator, words, lemma="see"):
    gloss = translator.lexicon.gloss(lemma, "VERB")
    return next(w for w in words if any(m.gloss == gloss for m in w.morphemes))


def named(profile=PROFILE, seed="7", **fixed):
    return Translator(profile, seed, fixed=fixed)


def test_symmetrical_infix_voice_with_imperfective_reduplication_and_tam_prefix():
    translator = named(
        alignment="symmetrical_voice",
        voice_affix_position="infix",
        tam_system="aspect3",
        tam_exponence="affix",
        tam_affix_position="prefix",
        imperfective_reduplication="yes",
    )
    words, _ = realize(translator, CLAUSES["progressive"])
    verb = verb_word(translator, words)
    assert [m.kind for m in verb.morphemes] == ["prefix", "reduplicant", "root", "infix"]
    assert [m.gloss for m in verb.morphemes][0] == "IMPF"
    assert verb.morphemes[3].gloss == "AF"


def test_verb_suffixes_apply_voice_then_tam_then_the_clitic_pronoun():
    translator = named(
        alignment="active_passive",
        voice_affix_position="suffix",
        pronoun_strategy="clitic_verb",
        pronoun_number="sg_pl",
        case_particles="none",
        tam_system="tense3",
        tam_exponence="affix",
        tam_affix_position="suffix",
    )
    words, _ = realize(translator, CLAUSES["negative_question"])
    verb = verb_word(translator, words)
    assert [m.gloss for m in verb.morphemes][1:] == ["AF", "PAST", "P1SG"]
    assert verb.morphemes[-1].kind == "clitic"


def test_ergative_sov_with_after_articles_orders_every_phrase_consistently():
    translator = named(
        alignment="ergative",
        clause_order="SOV",
        articles="both",
        article_position="after",
        modifier_position="before",
        possessor_position="before",
        noun_number="particle",
    )
    words, _ = realize(translator, CLAUSES["progressive"])
    glosses = [m.gloss for w in words for m in w.morphemes]
    dog = translator.lexicon.gloss("dog", "NOUN")
    child = translator.lexicon.gloss("child", "NOUN")
    big = translator.lexicon.gloss("big", "ADJ")
    see = translator.lexicon.gloss("see", "VERB")
    assert glosses.index(child) < glosses.index(big) < glosses.index(dog)
    assert glosses.index(dog) < glosses.index("PL") < glosses.index("DEF")
    assert glosses.index("DEF") < glosses.index(see)


def test_agentless_patient_is_promoted_across_voice_systems():
    for alignment in ("symmetrical_voice", "active_passive"):
        translator = named(alignment=alignment, voice_affix_position="prefix")
        words, _ = realize(translator, CLAUSES["agentless_patient"])
        verb = verb_word(translator, words)
        assert {"PF", "PASS"} & {m.gloss for m in verb.morphemes}, alignment
