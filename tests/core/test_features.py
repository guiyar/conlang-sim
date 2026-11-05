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


def test_catalog_rejects_an_excluded_feature_id():
    excluded = Feature("excluded_feature", "morphology", (Option("x"),), source_fields=("clause.kind",))
    with pytest.raises(ValueError, match="excluded feature appears"):
        FeatureCatalog((excluded,), excluded_features=(("excluded_feature", "not derivable"),))


def test_uniform_sampling_co_realizes_every_logically_allowed_option_pair():
    assignments = [CATALOG.sample(seed, uniform=True) for seed in range(10_000)]
    features = CATALOG.features
    observed = set()
    for assignment in assignments:
        for left_index, left in enumerate(features):
            left_value = assignment[left.id]
            if left_value is None:
                continue
            for right in features[left_index + 1:]:
                right_value = assignment[right.id]
                if right_value is not None:
                    observed.add((left.id, left_value, right.id, right_value))
    for left_index, left in enumerate(features):
        for right in features[left_index + 1:]:
            for left_option in left.options:
                for right_option in right.options:
                    fixed = {left.id: left_option.id, right.id: right_option.id}
                    if not _pair_is_possible(left, right, fixed):
                        continue
                    assert (left.id, left_option.id, right.id, right_option.id) in observed


def _pair_is_possible(left, right, fixed):
    for feature in (left, right):
        if feature.applies_if:
            for dependency, value in feature.applies_if.items():
                required = value if isinstance(value, (tuple, list, set, frozenset)) else (value,)
                if dependency in fixed and fixed[dependency] not in required:
                    return False
    for constraint in CATALOG.constraints:
        if not all(key in fixed for key in constraint.if_):
            continue
        if not all(
            fixed[key] in value if isinstance(value, (tuple, list, set, frozenset)) else fixed[key] == value
            for key, value in constraint.if_.items()
        ):
            continue
        for key, value in constraint.then.items():
            if key not in fixed:
                continue
            allowed = value if isinstance(value, (tuple, list, set, frozenset)) else (value,)
            if fixed[key] not in allowed:
                return False
    return True