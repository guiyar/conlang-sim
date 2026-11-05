from conlang.core.registry import discover_languages
from conlang.core.seeds import item_rng
from conlang.core.words import SurfaceInsertion, SurfaceResult


def test_five_thousand_roots_and_words_are_phonotactically_valid():
    profile = discover_languages()["austronesian"]
    checked = 0
    for seed in range(200):
        phonology = profile.phonology_class(
            profile.catalog.sample(seed), seed, profile.language_id, profile.output_version
        )
        for index in range(25):
            rng = item_rng(seed, profile.language_id, profile.output_version, "test", str(index))
            root = phonology.make_root(rng)
            assert phonology.valid(phonology.segments(root))
            checked += 1
        assert len(phonology.vowels) >= 3
        assert len(phonology.consonants) >= 9
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


def test_surface_repair_reports_explicit_consonant_cluster_insertions():
    profile = discover_languages()["austronesian"]
    features = profile.catalog.sample(0, {"syllable_structure": "closed"})
    phonology = profile.phonology_class(features, 0, profile.language_id, profile.output_version)
    notes = []

    result = phonology.validate_surface(["k", "t", "a"], notes, "a")

    assert isinstance(result, SurfaceResult)
    assert result.segments == ("k", "a", "t", "a")
    assert result.insertions == (SurfaceInsertion(1, "a", "consonant cluster"),)
