import pytest

from conlang.core.features import Constraint, Feature, FeatureCatalog, IncompatibleFeatures, Option
from conlang.languages.austronesian.catalog import CATALOG, EXCLUDED_FEATURES


def test_catalog_is_valid():
    assert CATALOG.validate_catalog()


@pytest.mark.stress
def test_random_samples_never_violate_constraints():
    for seed in range(10_000):
        assert not CATALOG._violations(CATALOG.sample(seed))


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
    catalog = FeatureCatalog(
        (Feature("a", "test", (Option("x"), Option("y")), meaning_bearing=False),)
    )
    assert catalog.sample(1)["a"] in {"x", "y"}
    with pytest.raises(ValueError, match="duplicate feature ID"):
        FeatureCatalog(
            (
                Feature("a", "test", (Option("x"),), meaning_bearing=False),
                Feature("a", "test", (Option("y"),), meaning_bearing=False),
            )
        )


def test_catalog_freezes_nested_feature_and_constraint_configuration():
    applies = {"a": ["x"]}
    constraint_if = {"a": ["x"]}
    constraint_then = {"a": ["x", "y"]}
    catalog = FeatureCatalog(
        (
            Feature("a", "test", (Option("x"), Option("y")), meaning_bearing=False),
            Feature(
                "b",
                "test",
                (Option("m"), Option("n")),
                applies_if=applies,
                meaning_bearing=False,
            ),
        ),
        (
            Constraint(
                "valid_a",
                constraint_if,
                constraint_then,
                "licensing",
                "The accepted value is explicitly represented.",
            ),
        ),
    )

    applies["a"].append("y")
    constraint_if["a"].append("y")
    constraint_then["a"].clear()

    assert catalog.features[1].applies_if["a"] == ("x",)
    assert catalog.constraints[0].if_["a"] == ("x",)
    assert catalog.constraints[0].then["a"] == ("x", "y")
    with pytest.raises(TypeError):
        catalog.features[1].applies_if["a"] = ("y",)
    with pytest.raises(TypeError):
        catalog.constraints[0].then["a"] = ("x",)
    with pytest.raises(AttributeError, match="configuration is immutable"):
        catalog.features = ()
    assert catalog.sample(7, {"a": "y"})["b"] is None


def test_seeded_feature_search_preserves_candidate_order_and_rng_consumption():
    catalog = FeatureCatalog(
        (
            Feature(
                "alignment",
                "test",
                (
                    Option("plain", 1),
                    Option("active", 2),
                    Option("ergative", 3),
                    Option("sym", 2),
                ),
                meaning_bearing=False,
            ),
            Feature(
                "voice",
                "test",
                (Option("none", 1), Option("mark", 2)),
                applies_if={"alignment": ("active", "ergative", "sym")},
                meaning_bearing=False,
            ),
            Feature("order", "test", (Option("svo", 1), Option("sov", 1)), meaning_bearing=False),
        ),
        (
            Constraint(
                "active_voice",
                {"alignment": "active"},
                {"voice": "mark"},
                "dependency",
                "Active alignment requires marked voice.",
            ),
            Constraint(
                "ergative_voice",
                {"alignment": "ergative"},
                {"voice": "mark"},
                "dependency",
                "Ergative alignment requires marked voice.",
            ),
        ),
        language_id="feature-golden",
        output_version=1,
    )

    assert [catalog.sample(seed) for seed in (0, 7, 42)] == [
        {"alignment": "sym", "voice": "none", "order": "svo"},
        {"alignment": "ergative", "voice": "mark", "order": "svo"},
        {"alignment": "plain", "voice": None, "order": "sov"},
    ]
    assert catalog.sample(7, {"alignment": "plain"}) == {
        "alignment": "plain",
        "voice": None,
        "order": "svo",
    }
    assert catalog.sample(7, uniform=True) == {
        "alignment": "ergative",
        "voice": "mark",
        "order": "svo",
    }


def test_excluded_features_are_not_catalogued():
    ids = {feature.id for feature in CATALOG.features}
    assert all(feature_id not in ids for feature_id, _ in EXCLUDED_FEATURES)


def test_catalog_rejects_an_excluded_feature_id():
    excluded = Feature(
        "excluded_feature", "morphology", (Option("x"),), source_fields=("clause.kind",)
    )
    with pytest.raises(ValueError, match="excluded feature appears"):
        FeatureCatalog((excluded,), excluded_features=(("excluded_feature", "not derivable"),))


@pytest.mark.stress
def test_uniform_sampling_co_realizes_every_logically_allowed_option_pair():
    assignments = [CATALOG.sample(seed, uniform=True) for seed in range(10_000)]
    features = CATALOG.features
    observed = set()
    for assignment in assignments:
        for left_index, left in enumerate(features):
            left_value = assignment[left.id]
            if left_value is None:
                continue
            for right in features[left_index + 1 :]:
                right_value = assignment[right.id]
                if right_value is not None:
                    observed.add((left.id, left_value, right.id, right_value))
    for left_index, left in enumerate(features):
        for right in features[left_index + 1 :]:
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
            fixed[key] in value
            if isinstance(value, (tuple, list, set, frozenset))
            else fixed[key] == value
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
