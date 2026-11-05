from conlang.core.base import Translator
from conlang.core.registry import discover_languages
from conlang.core.seeds import item_rng


def test_five_thousand_roots_and_words_are_phonotactically_valid():
    profile = discover_languages()["austronesian"]
    checked = 0
    for seed in range(200):
        translator = Translator(profile, seed)
        for index in range(25):
            rng = item_rng(seed, profile.language_id, profile.output_version, "test", str(index))
            root = translator.phonology.make_root(rng)
            assert translator.phonology.valid(translator.phonology.segments(root))
            checked += 1
        assert len(translator.phonology.vowels) >= 3
        assert len(translator.phonology.consonants) >= 9
    assert checked == 5_000


def test_tam_tables_are_total_and_unspecified_is_deterministic():
    from conlang.languages.austronesian.grammar import tam_category

    for tense in ("past", "present", "future", "UNSPECIFIED"):
        for perfect in (False, True):
            for progressive in (False, True):
                assert tam_category("tense3", tense, perfect, progressive) in {
                    "past",
                    "present",
                    "future",
                }
                assert tam_category("past_nonpast", tense, perfect, progressive) in {
                    "past",
                    "nonpast",
                }
                assert tam_category("aspect3", tense, perfect, progressive) in {
                    "contemplated",
                    "perfective",
                    "imperfective",
                }
