import pytest

from conlang.core.features import Constraint, Feature, FeatureCatalog, IncompatibleFeatures, Option
from conlang.languages.austronesian.catalog import CATALOG, EXCLUDED_FEATURES


def test_catalog_is_valid_and_all_options_reachable():
    assert CATALOG.validate_catalog()
    for seed in range(10_000):
        assignment = CATALOG.sample(seed)
        assert not CATALOG._violations(assignment)


def test_constraints_reject_impossible_fixed_values_with_ids():
    with pytest.raises(IncompatibleFeatures) as error:
        CATALOG.sample(4, {"prenasalized_stops": "yes", "stop_voicing": "voiceless_only"})
    assert "prenasal_requires_voiced_stops" in error.value.constraint_ids


def test_conditional_features_are_none_when_inactive_and_fixed_value_fails():
    assignment = CATALOG.sample(17, {"alignment": "plain"})
    assert assignment["voice_affix_position"] is None
    with pytest.raises(IncompatibleFeatures) as error:
        CATALOG.sample(17, {"alignment": "plain", "voice_affix_position": "prefix"})
    assert "applies_if:voice_affix_position" in error.value.constraint_ids


def test_small_fake_catalog_and_duplicate_rejection():
    catalog = FeatureCatalog((Feature("a", "test", (Option("x"), Option("y")), meaning_bearing=False),))
    assert catalog.sample(1)["a"] in {"x", "y"}
    with pytest.raises(ValueError, match="duplicate feature ID"):
        FeatureCatalog((Feature("a", "test", (Option("x"),), meaning_bearing=False),
                        Feature("a", "test", (Option("y"),), meaning_bearing=False)))


def test_excluded_features_are_not_catalogued():
    ids = {feature.id for feature in CATALOG.features}
    assert all(feature_id not in ids for feature_id, _ in EXCLUDED_FEATURES)