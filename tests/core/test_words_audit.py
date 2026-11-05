from dataclasses import FrozenInstanceError

import pytest

from conlang.core.audit import AuditedIR
from conlang.core.base import Translator
from conlang.core.ir import (
    Argument,
    Clause,
    ClauseLink,
    NounPhrase,
    PostModifier,
    SentenceIR,
    SourceToken,
    TokenDispositionLedger,
)
from conlang.core.ir_validation import (
    IRValidationError,
    finalize_sentence_ir,
    validate_sentence_ir,
)
from conlang.core.registry import discover_languages
from conlang.core.results import info, is_info
from conlang.core.words import Morpheme, SurfaceEdit, SurfaceInsertion, SurfaceResult, Word


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


def test_audited_ir_rejects_mutation_and_routes_disposition_to_ledger():
    token = SourceToken("dog", morph={"Number": ("Sing",)}, index=0)
    source = SentenceIR(Clause(), "dog", source_tokens=[token])
    ledger = TokenDispositionLedger(source.source_tokens)
    audited = AuditedIR(source, ledger)

    with pytest.raises(AttributeError, match="audited IR is read-only"):
        audited.value.clause.voice = "passive"
    with pytest.raises(AttributeError):
        audited.value.clause.arguments.append(Argument("subject", "other", NounPhrase("dog")))
    with pytest.raises(TypeError):
        audited.value.source_tokens[0].morph["Number"] = ("Plur",)

    audited.value.source_tokens[0].disposition = "realized"
    audited.value.source_tokens[0].disposition_reason = "emitted as a lexical word"
    assert token.disposition is None
    assert ledger.get(0) == ("realized", "emitted as a lexical word")
    ledger.sync(source.source_tokens)
    assert token.disposition == "realized"


def test_audit_normalizes_nested_np_and_clause_link_paths():
    source = SentenceIR(
        Clause(
            arguments=[
                Argument(
                    "subject",
                    "other",
                    NounPhrase(
                        "cup",
                        post_modifiers=[
                            PostModifier("prep", "of", NounPhrase("tea", definiteness="definite"))
                        ],
                    ),
                )
            ],
            links=[ClauseLink("complement", None, Clause(tense="past"))],
        ),
        "cup of tea",
    )
    audited = AuditedIR(source)
    _ = audited.value.clause.arguments[0].np.post_modifiers[0].np.definiteness
    assert audited.passes({"np.definiteness"})
    assert not audited.passes(set())

    audited = AuditedIR(source)
    _ = audited.value.clause.links[0].clause.tense
    assert audited.passes({"clause.tense"})
    assert not audited.passes(set())

    audited = AuditedIR(source)
    _ = audited.value.clause.arguments[0].np.post_modifiers[0].adposition
    assert audited.passes(set())


def test_sentence_ir_validation_checks_categories_and_token_accounting():
    valid = SentenceIR(
        Clause(arguments=[Argument("subject", "other", NounPhrase("dog"))]),
        "dog",
        source_tokens=[SourceToken("dog", index=0)],
    )
    assert validate_sentence_ir(valid) is valid

    invalid_category = SentenceIR(Clause(voice="middle"), "dog")
    with pytest.raises(IRValidationError, match="invalid clause voice"):
        validate_sentence_ir(invalid_category)

    invalid_argument = SentenceIR(
        Clause(arguments=[Argument("agent", "other", NounPhrase("dog"))]), "dog"
    )
    with pytest.raises(IRValidationError, match="invalid argument relation"):
        validate_sentence_ir(invalid_argument)

    duplicate_tokens = SentenceIR(
        Clause(),
        "dog dog",
        source_tokens=[SourceToken("dog", index=0), SourceToken("dog", index=0)],
    )
    with pytest.raises(IRValidationError, match="duplicate source token index"):
        validate_sentence_ir(duplicate_tokens)


def test_token_disposition_ledger_is_separate_until_synchronized():
    token = SourceToken("dog", index=3)
    ledger = TokenDispositionLedger([token])

    ledger.record(3, "realized")

    assert token.disposition is None
    assert ledger.get(3) == ("realized", None)
    ledger.sync([token])
    assert token.disposition == "realized"


def test_finalized_sentence_ir_is_an_immutable_snapshot():
    source = SentenceIR(
        Clause(
            arguments=[Argument("subject", "other", NounPhrase("dog"))],
        ),
        "dog",
        rules=[info("detail hidden by default")],
        source_tokens=[SourceToken("dog", morph={"Number": ("Sing",)}, index=0)],
    )

    finalized = finalize_sentence_ir(source)

    source.clause.arguments[0].np.head = "cat"
    source.source_tokens[0].morph["Number"] = ("Plur",)
    source.rules.append("later note")

    assert finalized.clause.arguments[0].np.head == "dog"
    assert finalized.source_tokens[0].morph["Number"] == ("Sing",)
    assert finalized.rules == ("detail hidden by default",)
    assert is_info(finalized.rules[0])
    with pytest.raises(FrozenInstanceError):
        finalized.clause.voice = "passive"
    with pytest.raises(AttributeError, match="finalized note is immutable"):
        finalized.rules[0].level = "notice"
    with pytest.raises(AttributeError):
        finalized.clause.arguments.append(Argument("object", "other", NounPhrase("cat")))
    with pytest.raises(TypeError):
        finalized.source_tokens[0].morph["Number"] = ("Plur",)


def test_infix_follows_complete_onset_and_surface_is_cached():
    word = Word(
        [
            Morpheme(("p",), "PRE", "prefix"),
            Morpheme(("k", "l", "a", "t"), "ROOT", "root"),
            Morpheme(("s",), "PL", "suffix"),
        ]
    )
    word.add_infix(Morpheme(("u", "m"), "AF", "infix"), 2)
    assert "".join(word.segments) == "pklumats"
    assert word.segmented() == "p-kl<um>at-s"
    assert word.gloss() == "PRE-ROOT<AF>-PL"
    calls = []
    first = word.surface(lambda segments, notes, vowel: calls.append(1) or segments)
    assert word.surface(lambda segments, notes, vowel: calls.append(1) or segments) == first
    assert len(calls) == 1
    assert word.gloss() == "PRE-ROOT<AF>-PL"


def test_invalid_infix_fallback_preserves_morpheme_sources():
    root = Morpheme(("k", "a", "t"), "ROOT", "root", sources=(3,))
    infix = Morpheme(("u",), "AF", "infix", sources=(7,))
    word = Word([root])

    word.add_infix(infix, onset_length=4)

    assert word.morphemes[-1].kind == "suffix"
    assert word.morphemes[-1].sources == (7,)
    assert word.sources == (3, 7)


def test_surface_validation_failure_does_not_finalize_word():
    word = Word([Morpheme(("k", "a", "t"), "ROOT", "root")])

    def reject(segments, notes, vowel):
        raise ValueError("invalid realization")

    with pytest.raises(ValueError, match="invalid realization"):
        word.surface(reject)

    assert word.realized is None
    assert word.surface() == "kat"
    assert word.realized is not None


def test_realized_word_is_immutable_and_rejects_construction_operations():
    word = Word([Morpheme(("k", "a", "t"), "ROOT", "root", sources=(4,))])

    realized = word.realize()

    assert realized is word.realized
    assert realized.surface() == "kat"
    assert realized.segments == ("k", "a", "t")
    assert realized.sources == (4,)
    with pytest.raises(FrozenInstanceError):
        realized.surface_form = "changed"
    with pytest.raises(FrozenInstanceError):
        realized.morphemes[0].segments = ("x",)
    with pytest.raises(RuntimeError, match="cannot modify"):
        word.add_suffix(Morpheme(("s",), "PL", "suffix"))


def test_surface_insertions_are_anchored_to_their_host_morpheme():
    word = Word([Morpheme(("k", "t"), "ROOT", "root", sources=(5,))])
    repair = SurfaceResult(("k", "a", "t"), (SurfaceInsertion(1, "a", "consonant cluster"),))

    realized = word.realize(lambda segments, notes, vowel: repair)

    assert realized.surface_edits == (SurfaceEdit(0, 1, "a", "consonant cluster"),)
    assert realized.morphemes[0].segments == ("k", "a", "t")
    assert realized.morphemes[0].sources == (5,)


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
