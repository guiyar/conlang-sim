"""Repository-owned regression tests for the supplied acceptance criteria."""

import re

import pytest

from conlang.core.base import Translator
from conlang.core.registry import discover_languages

PROFILE = discover_languages()["austronesian"]
BASE = {
    "syllable_structure": "open",
    "vowel_length": "none",
    "vowels": "v5",
    "word_initial_vowel": "no",
    "alignment": "plain",
    "case_particles": "none",
    "clause_order": "SVO",
    "tam_system": "past_nonpast",
    "tam_exponence": "particle",
    "noun_number": "none",
    "pronoun_strategy": "free",
    "modifier_position": "before",
    "demonstratives": "unmarked",
    "question": "particle_final",
    "negation": "clause_initial_particle",
    "possessor_position": "before",
    "pronoun_number": "sg_pl",
}


def make_translator(seed="7", **fixed):
    assignment = dict(BASE)
    assignment.update(fixed)
    return Translator(PROFILE, str(seed), fixed=assignment)


def output_lemmas(translator):
    return {entry["lemma"] for entry in translator.lexicon.export() if entry["lemma"]}


def test_probe_A2_short_roots_and_functions_on_reference_battery():
    battery = [
        "The child saw a bird near the river.",
        "The old man carried water to the house.",
    ]
    typical = 0
    for seed in range(150):
        translator = Translator(PROFILE, str(seed))
        for sentence in battery:
            translator.translate(sentence)
        entries = translator.lexicon.export()
        content = [
            len(entry["form"].replace("'", ""))
            for entry in entries
            if entry["category"] == "lexical" and entry["pos"] in {"NOUN", "VERB", "ADJ", "ADV"}
        ]
        functions = [
            len(entry["form"].replace("'", ""))
            for entry in entries
            if entry["category"] == "function"
        ]
        if (
            content
            and functions
            and sum(content) / len(content) <= 6
            and sum(functions) / len(functions) <= 2.6
        ):
            typical += 1
    assert typical / 150 >= 0.85


def test_probe_B1_function_morph_forms_are_unique():
    for seed in range(300):
        forms = make_translator(seed).function_morphs().values()
        assert len(forms) == len(set(forms)), seed


def test_probe_B3_does_not_export_an_unused_be_auxiliary():
    translator = make_translator()
    translator.translate("The child is with the bird.")
    assert "be" not in output_lemmas(translator)


def test_probe_C3_articles_are_not_lexical_roots():
    translator = make_translator(articles="both")
    translator.translate("The child saw a bird.")
    assert not any(
        entry["lemma"] in {"the", "a"} and entry["category"] == "lexical"
        for entry in translator.lexicon.export()
    )


def test_probe_D1_hyphenated_cardinal_composes_as_conlang_words():
    result = make_translator().translate("She saw twenty-one birds.")[0]
    glosses = [word.gloss() for word in result.words]
    assert any(glosses[index : index + 3] == ["TWO", "TEN", "ONE"] for index in range(len(glosses)))
    assert "twenty" not in [word.surface().lower() for word in result.words]


def test_probe_D3_a_hundred_is_numeral_not_an_indefinite_article():
    result = make_translator(articles="both").translate("She has a hundred cats.")[0]
    glosses = [word.gloss() for word in result.words]
    assert "HUNDRED" in glosses
    assert "INDEF" not in glosses


def test_probe_D4_number_word_root_uses_num_pos():
    translator = make_translator()
    translator.translate("She saw three birds.")
    entry = next(entry for entry in translator.lexicon.export() if entry["lemma"] == "three")
    assert (entry["category"], entry["pos"]) == ("lexical", "NUM")


def test_probe_D5_composed_numeral_is_deterministic():
    source = "She saw 305 birds and three dogs."
    first = make_translator("11").translate(source)[0]
    second = make_translator("11").translate(source)[0]
    assert [word.surface() for word in first.words] == [word.surface() for word in second.words]
    assert "305" in [word.surface() for word in first.words]


@pytest.mark.parametrize(
    "requirement_id,sentence,required_lemmas",
    [
        ("E2", "The cat and the dog ran.", {"cat", "dog", "run", "and"}),
        ("E3", "I think she left.", {"think", "leave"}),
        ("E4", "The man who called left.", {"man", "call"}),
        ("E5", "He didn't eat the food because it was cold.", {"eat", "food", "because", "cold"}),
        ("E6", "The happy dog sleeps.", {"happy", "dog", "sleep"}),
        ("E7", "A cup of tea is here.", {"cup", "tea", "of"}),
        ("E8", "Where is the dog?", {"where", "dog"}),
        ("E9", "She sat down and read the book.", {"sit", "read", "book", "and"}),
    ],
)
def test_probe_E2_to_E9_realize_required_lemmas_without_english_leak(
    requirement_id, sentence, required_lemmas
):
    translator = make_translator()
    results = translator.translate(sentence)
    assert required_lemmas <= output_lemmas(translator), (requirement_id, output_lemmas(translator))
    surfaces = {word.surface().lower() for result in results for word in result.words}
    leaked = {
        word.lower()
        for word in re.findall(r"[A-Za-z']+", sentence)
        if len(word) >= 4 and not word[0].isupper()
    } & surfaces
    assert not leaked, (requirement_id, leaked)


def test_probe_E10_content_tokens_are_realized_or_noted():
    from conlang.core.parser import _model

    nlp = _model()
    battery = [
        "The child saw two birds.",
        "My brother and I like fish.",
        "The old woman gave the boy a red apple.",
        "It rains in the morning.",
        "What do you want?",
        "The very quick fox runs quickly.",
        "She wants to go home because she is tired.",
        "The man standing there is my uncle.",
    ]
    for seed in (3, 9, 21):
        translator = make_translator(seed)
        for sentence in battery:
            results = translator.translate(sentence)
            surfaces = {word.surface() for result in results for word in result.words}
            notes = " ".join(rule for result in results for rule in result.rules).lower()
            lemmas = output_lemmas(translator)
            for token in nlp(sentence):
                if token.pos_ in {"NOUN", "VERB", "ADJ", "ADV", "PROPN"}:
                    assert (
                        token.lemma_.lower() in lemmas
                        or token.text in surfaces
                        or token.text.lower() in notes
                    ), (seed, sentence, token.text)


def test_probe_F2_tam_particle_immediately_precedes_verb_in_major_orders():
    for order, sentence, verb in (
        ("SVO", "The dog ran.", "RUN"),
        ("SOV", "The dog ate the fish.", "EAT"),
        ("VSO", "The dog ate the fish.", "EAT"),
    ):
        glosses = [
            word.gloss()
            for word in make_translator(clause_order=order).translate(sentence)[0].words
        ]
        verb_index = next(index for index, gloss in enumerate(glosses) if verb in gloss)
        assert verb_index > 0 and glosses[verb_index - 1] in {
            "PAST",
            "PRESENT",
            "NONPAST",
            "FUTURE",
        }, (order, glosses)


def test_probe_F11_all_generated_output_is_ascii():
    result = make_translator().translate("The big dogs run.")[0]
    assert all(word.surface().isascii() for word in result.words)
