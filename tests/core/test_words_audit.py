from conlang.core.audit import AuditedIR
from conlang.core.ir import Argument, Clause, NounPhrase, SentenceIR
from conlang.core.registry import discover_languages
from conlang.core.base import Translator
from conlang.core.words import Morpheme, Word


def test_austronesian_realization_audit_and_seed_stability():
    profile = discover_languages()["austronesian"]
    source = SentenceIR(Clause(predicate="see", predicate_pos="VERB", tense="past", transitivity=True,
                               arguments=[Argument("subject", "agent", NounPhrase("child", number="singular")),
                                          Argument("object", "patient", NounPhrase("dog", number="plural"))]),
                        "The child saw dogs.")
    for seed in range(200):
        translator = Translator(profile, seed)
        audited = AuditedIR(source)
        words, _ = translator.realizer.realize(audited.value, translator.lexicon)
        allowed = {field for feature in profile.catalog.features if feature.meaning_bearing and translator.features[feature.id] is not None for field in feature.source_fields}
        assert audited.passes(allowed)
        for word in words:
            form = word.surface(translator.phonology.validate_surface, translator.phonology.epenthetic_vowel)
            assert translator.phonology.valid(translator.phonology.segments(form))
            assert translator.phonology.segments(form) == list(word.segments)
            assert len(word.segmented().split("-")) == len(word.gloss().split("-"))


def test_audit_rejects_undeclared_grammatical_read():
    ir = SentenceIR(Clause(predicate="walk"), "walk")
    audited = AuditedIR(ir)
    _ = audited.value.clause.voice
    assert not audited.passes(set())


def test_infix_follows_complete_onset_and_surface_is_cached():
    word = Word([Morpheme(("k", "l", "a", "t"), "ROOT", "root")])
    word.add_infix(Morpheme(("u", "m"), "AF", "infix"), 2)
    assert "".join(word.segments) == "klumat"
    calls = []
    first = word.surface(lambda segments, notes, vowel: calls.append(1) or segments)
    assert word.surface(lambda segments, notes, vowel: calls.append(1) or segments) == first
    assert len(calls) == 1
    assert word.gloss() == "ROOT-AF"


def test_invalid_morpheme_kind_rejected():
    try:
        Morpheme(("a",), "X", "circumfix")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid morpheme kind was accepted")


def test_fragment_generation_records_fallback_span_and_preserves_literal_tokens():
    profile = discover_languages()["austronesian"]
    result = Translator(profile, 5).translate("!!!")
    assert result.fallback_spans == [(0, 3)]
    assert [word.surface() for word in result.words] == ["!", "!", "!"]