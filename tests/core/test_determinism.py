from conlang.core.base import Translator
from conlang.core.lexicon import Lexicon
from conlang.core.registry import discover_languages
from conlang.core.render import render


def test_same_seed_input_repeats_identically():
    profile = discover_languages()["austronesian"]
    outputs = [
        render(Translator(profile, 42).translate("The children saw a bird.")[0].words)
        for _ in range(2)
    ]
    assert outputs[0] == outputs[1]


def test_lexical_request_order_does_not_change_roots():
    profile = discover_languages()["austronesian"]
    first = Translator(profile, 23)
    second = Translator(profile, 23)
    dog_first = first.lexicon.root("dog", "NOUN")
    first.lexicon.root("unrelated", "ADJ")
    second.lexicon.root("unrelated", "ADJ")
    dog_second = second.lexicon.root("dog", "NOUN")
    assert dog_first == dog_second
    assert first.lexicon.root("dog", "VERB") != dog_first


def test_feature_assignments_and_output_vary_across_seed_sweep():
    profile = discover_languages()["austronesian"]
    assignments = [profile.catalog.sample(seed) for seed in range(200)]
    for feature in profile.catalog.features:
        assert len({assignment[feature.id] for assignment in assignments}) > 1, feature.id
    outputs = {
        render(Translator(profile, seed).translate("We see the birds.")[0].words)
        for seed in range(200)
    }
    assert len(outputs) >= 50


def test_lexicon_separates_language_ids():
    profile = discover_languages()["austronesian"]
    phonology = profile.phonology_class(
        profile.catalog.sample(7), 7, "other_language", profile.output_version
    )
    first = Lexicon(
        7,
        profile.language_id,
        profile.output_version,
        profile.phonology_class(
            profile.catalog.sample(7), 7, profile.language_id, profile.output_version
        ),
    )
    other = Lexicon(7, "other_language", profile.output_version, phonology)
    assert first.root("bird", "NOUN") != other.root("bird", "NOUN")


def test_gloss_is_invariant_when_only_form_parameters_change():
    profile = discover_languages()["austronesian"]
    assignment = profile.catalog.sample(109)
    meaning_features = {
        feature.id: assignment[feature.id]
        for feature in profile.catalog.features
        if feature.meaning_bearing and assignment[feature.id] is not None
    }
    sentence = "The children were seen by Mina."
    outputs = []
    for seed in range(20):
        result = Translator(profile, seed, fixed=meaning_features).translate(sentence)[0]
        outputs.append([word.gloss() for word in result.words])
    assert len({tuple(output) for output in outputs}) == 1
