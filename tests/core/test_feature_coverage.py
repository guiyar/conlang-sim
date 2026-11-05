"""Assignment-level coverage generated from the Austronesian catalogue; no parsing or realization."""

import pytest

from conlang.core.features import IncompatibleFeatures
from conlang.languages.austronesian.catalog import CATALOG

SEED = 42


def _as_tuple(value):
    return value if isinstance(value, (tuple, list, set, frozenset)) else (value,)


FEATURE_OPTIONS = [
    pytest.param(feature.id, option.id, id=f"{feature.id}={option.id}")
    for feature in CATALOG.features
    for option in feature.options
]
CONDITIONAL = [f for f in CATALOG.features if f.applies_if]


@pytest.mark.parametrize(("feature_id", "option_id"), FEATURE_OPTIONS)
def test_every_feature_option_is_selectable(feature_id, option_id):
    assignment = CATALOG.sample(SEED, fixed={feature_id: option_id})
    assert assignment[feature_id] == option_id
    assert not CATALOG._violations(assignment)


@pytest.mark.parametrize(("feature_id", "option_id"), FEATURE_OPTIONS)
def test_every_option_is_reachable_without_sampling(feature_id, option_id):
    assert CATALOG._find({feature_id: option_id}, 0, {}) is not None


@pytest.mark.parametrize("feature", CONDITIONAL, ids=lambda f: f.id)
def test_fixing_a_conditional_feature_activates_its_parents(feature):
    option = feature.options[0].id
    assignment = CATALOG.sample(SEED, fixed={feature.id: option})
    assert assignment[feature.id] == option
    for parent, accepted in feature.applies_if.items():
        assert assignment[parent] in _as_tuple(accepted)


@pytest.mark.parametrize("feature", CONDITIONAL, ids=lambda f: f.id)
def test_conditional_feature_is_none_when_parent_is_outside_condition(feature):
    parent, accepted = next(iter(feature.applies_if.items()))
    parent_feature = next(f for f in CATALOG.features if f.id == parent)
    outside = [o.id for o in parent_feature.options if o.id not in _as_tuple(accepted)]
    assert outside, "condition covers every parent option"
    assignment = CATALOG.sample(SEED, fixed={parent: outside[0]})
    assert assignment[feature.id] is None


def test_fixing_a_conditional_feature_under_a_bad_parent_is_rejected():
    # Rejection backtracks through every earlier feature, so only the earliest conditional is cheap.
    feature = CONDITIONAL[0]
    parent, accepted = next(iter(feature.applies_if.items()))
    parent_feature = next(f for f in CATALOG.features if f.id == parent)
    outside = next(o.id for o in parent_feature.options if o.id not in _as_tuple(accepted))
    with pytest.raises(IncompatibleFeatures) as error:
        CATALOG.sample(SEED, fixed={parent: outside, feature.id: feature.options[0].id})
    assert f"applies_if:{feature.id}" in error.value.constraint_ids


def _violating_fixed(constraint):
    fixed = {key: _as_tuple(value)[0] for key, value in constraint.if_.items()}
    key, allowed = next(iter(constraint.then.items()))
    feature = next(f for f in CATALOG.features if f.id == key)
    fixed[key] = next(o.id for o in feature.options if o.id not in _as_tuple(allowed))
    return fixed


@pytest.mark.parametrize("constraint", CATALOG.constraints, ids=lambda c: c.id)
def test_every_constraint_rejects_a_violating_assignment(constraint):
    with pytest.raises(IncompatibleFeatures) as error:
        CATALOG.sample(SEED, fixed=_violating_fixed(constraint))
    assert constraint.id in error.value.constraint_ids


@pytest.mark.parametrize(("feature_id", "option_id"), FEATURE_OPTIONS[::5])
def test_same_seed_and_overrides_give_identical_assignments(feature_id, option_id):
    fixed = {feature_id: option_id}
    assert CATALOG.sample(7, fixed) == CATALOG.sample(7, fixed)


def test_unknown_fixed_option_is_rejected():
    with pytest.raises(ValueError, match="unknown fixed feature option"):
        CATALOG.sample(SEED, fixed={"noun_number": "nonexistent"})
