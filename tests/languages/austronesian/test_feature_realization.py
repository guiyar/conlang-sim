"""Each morphosyntactic option, forced via `fixed`, realized against a purpose-built IR (no spaCy)."""

import pytest

from conlang.core.base import Translator
from conlang.core.ir import (
    Argument,
    Clause,
    Modifier,
    NounPhrase,
    Possessor,
    SentenceIR,
)
from conlang.languages.austronesian.catalog import CATALOG

SEED = 7


def options(feature_id):
    feature = next(f for f in CATALOG.features if f.id == feature_id)
    return [option.id for option in feature.options]


def realize(profile, clause, **fixed):
    translator = Translator(profile, SEED, fixed=fixed)
    words, _ = translator.realizer.realize(SentenceIR(clause, "test"), translator.lexicon)
    return translator, words


def glosses(words):
    return [m.gloss for w in words for m in w.morphemes]


def index_of(words, gloss):
    return next(i for i, w in enumerate(words) if any(m.gloss == gloss for m in w.morphemes))


def morpheme(words, gloss):
    return next(m for w in words for m in w.morphemes if m.gloss == gloss)


def noun(head, **kwargs):
    return NounPhrase(head, number="singular", **kwargs)


def intransitive(subject, **clause_kwargs):
    return Clause(
        predicate="run",
        predicate_pos="VERB",
        arguments=[Argument("subject", "agent", subject)],
        **clause_kwargs,
    )


def transitive(subject_role="agent", **clause_kwargs):
    return Clause(
        predicate="see",
        predicate_pos="VERB",
        transitivity=True,
        arguments=[
            Argument("subject", subject_role, noun("child")),
            Argument("object", "patient" if subject_role == "agent" else "agent", noun("dog")),
        ],
        **clause_kwargs,
    )


def root_gloss(translator, lemma, pos):
    return translator.lexicon.gloss(lemma, pos)


@pytest.mark.parametrize("option", options("noun_number"))
def test_noun_number_marks_only_plural_nouns(profile, option):
    translator, plural = realize(
        profile, intransitive(NounPhrase("dog", number="plural")), noun_number=option
    )
    _, singular = realize(profile, intransitive(noun("dog")), noun_number=option)
    assert not {"RED", "PL"} & set(glosses(singular))
    if option == "none":
        assert not {"RED", "PL"} & set(glosses(plural))
    elif option == "particle":
        assert "PL" in glosses(plural)
    else:
        root = morpheme(plural, root_gloss(translator, "dog", "NOUN"))
        copy = morpheme(plural, "RED")
        assert copy.kind == "reduplicant"
        if option == "full_reduplication":
            assert copy.segments == root.segments
        else:
            assert root.segments[: len(copy.segments)] == copy.segments
            assert len(copy.segments) < len(root.segments)
    assert "PL" not in glosses(plural) or option == "particle"


@pytest.mark.parametrize("option", options("alignment"))
def test_alignment_selects_voice_and_case_marking(profile, option):
    t, active = realize(profile, transitive(), alignment=option)
    _, passive = realize(profile, transitive(voice="passive"), alignment=option)
    _, patient_pivot = realize(profile, transitive(subject_role="patient"), alignment=option)
    voice = {"AF", "PF", "PASS"}
    if option == "plain":
        assert not voice & set(glosses(active))
    elif option == "active_passive":
        assert "AF" in glosses(active) and "PASS" not in glosses(active)
        assert "PASS" in glosses(passive)
    elif option == "symmetrical_voice":
        assert "AF" in glosses(active)
        assert "PF" in glosses(patient_pivot)
        assert {"NOM", "GEN"} <= set(glosses(active))
    elif option == "ergative":
        assert "ERG" in glosses(active)
        assert not voice & set(glosses(active))
    else:
        pytest.fail(f"no realization test for alignment={option}")


@pytest.mark.parametrize("position", options("voice_affix_position"))
def test_voice_affix_position(profile, position):
    translator, words = realize(
        profile, transitive(), alignment="active_passive", voice_affix_position=position
    )
    verb = next(w for w in words if root_gloss(translator, "see", "VERB") in glosses([w]))
    assert next(m for m in verb.morphemes if m.gloss == "AF").kind == position


@pytest.mark.parametrize("option", options("case_particles"))
def test_case_particles_are_emitted_only_when_preposed(profile, option):
    fixed = {"alignment": "ergative" if option == "preposed" else "plain"}
    _, words = realize(profile, transitive(), case_particles=option, **fixed)
    assert ("ERG" in glosses(words)) == (option == "preposed")


EXPECTED_TAM = {
    ("tense3", "past"): "PAST",
    ("tense3", "future"): "FUTURE",
    ("past_nonpast", "past"): "PAST",
    ("past_nonpast", "future"): "NONPAST",
    ("aspect3", "past"): "PERF",
    ("aspect3", "future"): "CONT",
}


@pytest.mark.parametrize("exponence", options("tam_exponence"))
@pytest.mark.parametrize("system", options("tam_system"))
@pytest.mark.parametrize("tense", ["past", "future"])
def test_tam_system_and_exponence(profile, system, exponence, tense):
    translator, words = realize(
        profile, intransitive(noun("dog"), tense=tense), tam_system=system, tam_exponence=exponence
    )
    expected = EXPECTED_TAM[(system, tense)]
    assert expected in glosses(words)
    marker = morpheme(words, expected)
    if exponence == "particle":
        assert marker.kind == "particle"
    else:
        assert marker.kind in {"prefix", "suffix"}


@pytest.mark.parametrize("position", options("tam_affix_position"))
def test_tam_affix_position(profile, position):
    _, words = realize(
        profile,
        intransitive(noun("dog"), tense="past"),
        tam_exponence="affix",
        tam_affix_position=position,
    )
    assert morpheme(words, "PAST").kind == position


@pytest.mark.parametrize("option", options("imperfective_reduplication"))
def test_imperfective_reduplication_applies_to_progressive_verbs(profile, option):
    _, progressive = realize(
        profile,
        intransitive(noun("dog"), progressive=True),
        tam_system="aspect3",
        imperfective_reduplication=option,
    )
    _, perfective = realize(
        profile,
        intransitive(noun("dog"), tense="past"),
        tam_system="aspect3",
        imperfective_reduplication=option,
    )
    assert ("RED" in glosses(progressive)) == (option == "yes")
    assert "RED" not in glosses(perfective)


@pytest.mark.parametrize("option", options("question"))
def test_question_particle_position(profile, option):
    _, words = realize(profile, intransitive(noun("dog"), mood="interrogative"), question=option)
    if option == "none":
        assert "QUESTION" not in glosses(words)
    elif option == "particle_initial":
        assert index_of(words, "QUESTION") == 0
    else:
        assert index_of(words, "QUESTION") == len(words) - 1


@pytest.mark.parametrize("option", options("negation"))
def test_negation_particle_position(profile, option):
    translator, words = realize(
        profile, intransitive(noun("dog"), polarity="negative"), negation=option
    )
    verb = index_of(words, root_gloss(translator, "run", "VERB"))
    negation = index_of(words, "NEG")
    if option == "clause_initial_particle":
        assert negation == 0
    else:
        assert negation == verb - 1


@pytest.mark.parametrize("option", options("articles"))
def test_articles_follow_the_system(profile, option):
    subject = noun("dog", definiteness="definite")
    clause = Clause(
        predicate="see",
        predicate_pos="VERB",
        transitivity=True,
        arguments=[
            Argument("subject", "agent", subject),
            Argument("object", "patient", noun("bird", definiteness="indefinite")),
        ],
    )
    _, words = realize(profile, clause, articles=option)
    assert ("DEF" in glosses(words)) == (option in {"both", "definite_only"})
    assert ("INDEF" in glosses(words)) == (option in {"both", "indefinite_only"})


@pytest.mark.parametrize("option", options("article_position"))
def test_article_position(profile, option):
    translator, words = realize(
        profile,
        intransitive(noun("dog", definiteness="definite")),
        articles="definite_only",
        article_position=option,
    )
    article = index_of(words, "DEF")
    head = index_of(words, root_gloss(translator, "dog", "NOUN"))
    assert (article < head) == (option == "before")


@pytest.mark.parametrize("option", options("clause_order"))
def test_clause_order(profile, option):
    translator, words = realize(profile, transitive(), clause_order=option)
    positions = {
        role: index_of(words, root_gloss(translator, lemma, pos))
        for role, lemma, pos in (("V", "see", "VERB"), ("S", "child", "NOUN"), ("O", "dog", "NOUN"))
    }
    assert "".join(sorted(positions, key=positions.get)) == option


@pytest.mark.parametrize("option", options("pronoun_strategy"))
def test_pronoun_strategy(profile, option):
    pronoun = NounPhrase("I", kind="pronoun", person="1", number="singular")
    translator, words = realize(
        profile,
        intransitive(pronoun),
        pronoun_strategy=option,
        pronoun_number="sg_pl",
        alignment="plain",
    )
    verb_gloss = root_gloss(translator, "run", "VERB")
    verb = next(w for w in words if verb_gloss in glosses([w]))
    clitics = [m for w in words for m in w.morphemes if m.kind == "clitic"]
    if option == "free":
        assert not clitics
        assert "P1SG" in [m.gloss for w in words if len(w.morphemes) == 1 for m in w.morphemes]
    else:
        assert [m.gloss for m in clitics] == ["P1SG"]
        if option == "clitic_verb":
            assert any(m.kind == "clitic" for m in verb.morphemes)


@pytest.mark.parametrize("option", options("pronoun_number"))
def test_pronoun_number(profile, option):
    pronoun = NounPhrase("we", kind="pronoun", person="1", number="plural")
    _, words = realize(profile, intransitive(pronoun), pronoun_number=option)
    assert ("P1PL" if option == "sg_pl" else "P1") in glosses(words)


@pytest.mark.parametrize("option", options("modifier_position"))
def test_modifier_position(profile, option):
    translator, words = realize(
        profile,
        intransitive(noun("dog", modifiers=[Modifier("big", "big", pos="ADJ")])),
        modifier_position=option,
    )
    head = index_of(words, root_gloss(translator, "dog", "NOUN"))
    modifier = index_of(words, root_gloss(translator, "big", "ADJ"))
    assert (modifier < head) == (option == "before")


@pytest.mark.parametrize("option", options("linker"))
def test_linker(profile, option):
    translator, words = realize(
        profile,
        intransitive(noun("dog", modifiers=[Modifier("big", "big", pos="ADJ")])),
        modifier_position="after",
        linker=option,
    )
    assert ("LINK" in glosses(words)) == (option == "particle")
    if option == "particle":
        head = index_of(words, root_gloss(translator, "dog", "NOUN"))
        assert index_of(words, "LINK") == head + 1


@pytest.mark.parametrize("option", options("possessor_position"))
def test_possessor_position(profile, option):
    translator, words = realize(
        profile,
        intransitive(noun("dog", possessor=Possessor(noun("child")))),
        possessor_position=option,
    )
    head = index_of(words, root_gloss(translator, "dog", "NOUN"))
    possessor = index_of(words, root_gloss(translator, "child", "NOUN"))
    assert (possessor < head) == (option == "before")


@pytest.mark.parametrize("option", options("demonstratives"))
def test_demonstratives(profile, option):
    _, words = realize(
        profile, intransitive(noun("dog", demonstrative="proximal")), demonstratives=option
    )
    assert ("PROX" in glosses(words)) == (option == "two_way")


def test_every_morphosyntactic_feature_has_a_realization_test():
    covered = {
        "noun_number", "alignment", "voice_affix_position", "case_particles", "tam_system",
        "tam_exponence", "tam_affix_position", "imperfective_reduplication", "question",
        "negation", "articles", "article_position", "clause_order", "pronoun_strategy",
        "pronoun_number", "modifier_position", "linker", "possessor_position",
        "demonstratives",
    }  # fmt: skip
    morphosyntax = {f.id for f in CATALOG.features if f.group == "morphosyntax"}
    assert morphosyntax == covered


FEATURE_OPTIONS = [(f.id, o.id) for f in CATALOG.features for o in f.options]


@pytest.mark.parametrize(("feature_id", "option_id"), FEATURE_OPTIONS)
def test_every_option_realizes_a_rich_clause_with_valid_surfaces(profile, feature_id, option_id):
    subject = NounPhrase(
        "dog",
        number="plural",
        definiteness="definite",
        demonstrative="proximal",
        modifiers=[Modifier("big", "big", pos="ADJ")],
        possessor=Possessor(noun("child")),
    )
    clause = Clause(
        predicate="see",
        predicate_pos="VERB",
        transitivity=True,
        tense="past",
        polarity="negative",
        mood="interrogative",
        arguments=[
            Argument("subject", "agent", subject),
            Argument("object", "patient", noun("bird", definiteness="indefinite")),
        ],
    )
    fixed = CATALOG._find({feature_id: option_id}, 0, {})
    fixed = {key: value for key, value in fixed.items() if value is not None}
    translator = Translator(profile, 97, fixed=fixed)
    words, rules = translator.realizer.realize(SentenceIR(clause, "test"), translator.lexicon)
    assert "Unexpected" not in " ".join(rules)
    phonology = translator.phonology
    for word in words:
        surface = word.surface(phonology.validate_surface, phonology.epenthetic_vowel)
        assert phonology.valid(phonology.segments(surface)), surface
