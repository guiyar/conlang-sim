from conlang.core.audit import AuditedIR
from conlang.core.base import Translator
from conlang.core.ir import Argument, Clause, NounPhrase, SentenceIR
from conlang.core.registry import discover_languages
from conlang.core.words import Morpheme, Word


def test_austronesian_realization_audit_and_seed_stability():
    profile = discover_languages()["austronesian"]
    source = SentenceIR(
        Clause(
            predicate="see",
            predicate_pos="VERB",
            tense="past",
            transitivity=True,
            arguments=[
                Argument("subject", "agent", NounPhrase("child", number="singular")),
                Argument("object", "patient", NounPhrase("dog", number="plural")),
            ],
        ),
        "The child saw dogs.",
    )
    for seed in range(200):
        translator = Translator(profile, seed)
        audited = AuditedIR(source)
        words, _ = translator.realizer.realize(audited.value, translator.lexicon)
        allowed = {
            field
            for feature in profile.catalog.features
            if feature.meaning_bearing and translator.features[feature.id] is not None
            for field in feature.source_fields
        }
        assert audited.passes(allowed)
        for word in words:
            form = word.surface(
                translator.phonology.validate_surface, translator.phonology.epenthetic_vowel
            )
            assert translator.phonology.valid(translator.phonology.segments(form))
            assert translator.phonology.segments(form) == list(word.segments)
            assert len(word.segmented().split("-")) == len(word.gloss().split("-"))


def test_audit_rejects_undeclared_grammatical_read():
    ir = SentenceIR(Clause(predicate="walk"), "walk")
    audited = AuditedIR(ir)
    _ = audited.value.clause.voice
    assert not audited.passes(set())


def test_audit_rejects_new_meaning_bearing_ir_fields_without_declarations():
    source = SentenceIR(
        Clause(
            arguments=[Argument("subject", "other", NounPhrase("dog", definiteness="definite"))]
        ),
        "the dog",
    )
    audited = AuditedIR(source)
    _ = audited.value.clause.arguments[0].np.definiteness
    assert not audited.passes(set())
    assert audited.passes({"np.definiteness"})

    audited = AuditedIR(source)
    _ = audited.value.clause.arguments[0].np.post_modifiers
    assert audited.passes(set())


def test_audit_accepts_new_structural_ir_fields_without_feature_declarations():
    source = SentenceIR(
        Clause(
            links=[],
            arguments=[
                Argument("subject", "other", NounPhrase("dog", pos="NOUN", numeral_value=5))
            ],
        ),
        "dog",
    )
    audited = AuditedIR(source)
    _ = audited.value.clause.arguments[0].np.pos
    _ = audited.value.clause.arguments[0].np.numeral_value
    _ = audited.value.clause.links
    assert audited.passes(set())


def test_infix_follows_complete_onset_and_surface_is_cached():
    word = Word([Morpheme(("k", "l", "a", "t"), "ROOT", "root")])
    word.add_infix(Morpheme(("u", "m"), "AF", "infix"), 2)
    assert "".join(word.segments) == "klumat"
    calls = []
    first = word.surface(lambda segments, notes, vowel: calls.append(1) or segments)
    assert word.surface(lambda segments, notes, vowel: calls.append(1) or segments) == first
    assert len(calls) == 1
    assert word.gloss() == "ROOT<AF>"


def test_invalid_morpheme_kind_rejected():
    try:
        Morpheme(("a",), "X", "circumfix")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid morpheme kind was accepted")


def test_punctuation_only_input_uses_empty_fallback_words():
    profile = discover_languages()["austronesian"]
    result = Translator(profile, 5).translate("!!!")[0]
    assert result.fallback_spans == [(0, 3)]
    assert result.words == []
