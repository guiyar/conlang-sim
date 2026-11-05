"""Generic constrained dialect-feature assignment."""

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, TypeAlias

from .ir import VALID_SOURCE_FIELDS
from .seeds import item_rng

VALID_STATUSES = frozenset({"attested", "adapted", "invented"})
VALID_REASONS = frozenset({"licensing", "dependency", "exclusivity", "ambiguity"})
FeatureCondition: TypeAlias = str | tuple[str, ...] | list[str] | set[str] | frozenset[str]


def _freeze_conditions(conditions):
    frozen = {}
    for feature_id, values in conditions.items():
        if isinstance(values, (tuple, list)):
            frozen[feature_id] = tuple(values)
        elif isinstance(values, (set, frozenset)):
            frozen[feature_id] = tuple(sorted(values))
        else:
            frozen[feature_id] = values
    return MappingProxyType(frozen)


@dataclass(frozen=True)
class Option:
    id: str
    weight: float = 1.0
    attested_in: tuple[str, ...] = ()
    status: str = "invented"
    note: str = ""

    def __post_init__(self):
        object.__setattr__(self, "attested_in", tuple(self.attested_in))


@dataclass(frozen=True)
class Feature:
    id: str
    group: str
    options: tuple[Option, ...]
    applies_if: Mapping[str, FeatureCondition] | None = None
    meaning_bearing: bool = True
    source_fields: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "options", tuple(self.options))
        object.__setattr__(
            self,
            "applies_if",
            None if self.applies_if is None else _freeze_conditions(self.applies_if),
        )
        object.__setattr__(self, "source_fields", tuple(self.source_fields))


@dataclass(frozen=True)
class Constraint:
    id: str
    if_: Mapping[str, FeatureCondition]
    then: Mapping[str, FeatureCondition]
    reason: str
    justification: str

    def __post_init__(self):
        object.__setattr__(self, "if_", _freeze_conditions(self.if_))
        object.__setattr__(self, "then", _freeze_conditions(self.then))


class IncompatibleFeatures(ValueError):
    def __init__(self, constraint_ids):
        self.constraint_ids = tuple(sorted(set(constraint_ids)))
        super().__init__("incompatible feature assignment: " + ", ".join(self.constraint_ids))


class FeatureCatalog:
    def __init__(
        self,
        features,
        constraints=(),
        excluded_features=(),
        language_id="feature-catalog",
        output_version=1,
    ):
        self._validated = False
        self.features = tuple(features)
        self.constraints = tuple(constraints)
        self.excluded_features = tuple(
            tuple(item) if isinstance(item, list) else item for item in excluded_features
        )
        self.language_id = language_id
        self.output_version = output_version
        self.validate_catalog()
        self._validated = True

    def __setattr__(self, name, value):
        if self.__dict__.get("_validated", False):
            raise AttributeError("feature catalog configuration is immutable")
        object.__setattr__(self, name, value)

    @staticmethod
    def _active(feature, assignment):
        return feature.applies_if is None or all(
            assignment.get(k) in v
            if isinstance(v, (tuple, list, set, frozenset))
            else assignment.get(k) == v
            for k, v in feature.applies_if.items()
        )

    def _violations(self, assignment, partial=False):
        violations = []
        for constraint in self.constraints:
            keys = set(constraint.if_) | set(constraint.then)
            if any(k not in assignment for k in keys):
                if partial:
                    continue
            if any(assignment.get(k) is None for k in keys):
                continue
            if all(
                assignment.get(k) in v
                if isinstance(v, (tuple, list, set, frozenset))
                else assignment.get(k) == v
                for k, v in constraint.if_.items()
            ):
                if not all(
                    assignment.get(k) in v
                    if isinstance(v, (tuple, list, set, frozenset))
                    else assignment.get(k) == v
                    for k, v in constraint.then.items()
                ):
                    violations.append(constraint.id)
        return violations

    def validate_catalog(self):
        ids = [f.id for f in self.features]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate feature ID")
        option_ids = {}
        for index, feature in enumerate(self.features):
            if not feature.options:
                raise ValueError(f"feature {feature.id} has no options")
            options = [o.id for o in feature.options]
            if len(options) != len(set(options)):
                raise ValueError(f"duplicate option ID in {feature.id}")
            option_ids[feature.id] = set(options)
            if feature.meaning_bearing and not feature.source_fields:
                raise ValueError(f"meaning-bearing feature {feature.id} needs source_fields")
            if not feature.meaning_bearing and feature.source_fields:
                raise ValueError(f"phonological feature {feature.id} cannot declare source_fields")
            invalid_fields = set(feature.source_fields) - VALID_SOURCE_FIELDS
            if invalid_fields:
                raise ValueError(
                    f"invalid source_fields in {feature.id}: {', '.join(sorted(invalid_fields))}"
                )
            if feature.applies_if:
                for dep, value in feature.applies_if.items():
                    if dep not in ids[:index]:
                        raise ValueError(f"{feature.id} depends on non-earlier feature {dep}")
                    accepted = (
                        value if isinstance(value, (tuple, list, set, frozenset)) else (value,)
                    )
                    if not set(accepted) <= option_ids[dep]:
                        raise ValueError(f"invalid dependency option {dep}={value}")
        if len({c.id for c in self.constraints}) != len(self.constraints):
            raise ValueError("duplicate constraint ID")
        for constraint in self.constraints:
            if constraint.reason not in VALID_REASONS or not constraint.justification.strip():
                raise ValueError(f"invalid constraint metadata: {constraint.id}")
            for mapping in (constraint.if_, constraint.then):
                for fid, value in mapping.items():
                    accepted = (
                        value if isinstance(value, (tuple, list, set, frozenset)) else (value,)
                    )
                    if fid not in option_ids or not set(accepted) <= option_ids[fid]:
                        raise ValueError(
                            f"invalid reference in constraint {constraint.id}: {fid}={value}"
                        )
        excluded_ids = {
            item[0] if isinstance(item, (tuple, list)) else item for item in self.excluded_features
        }
        if any(feature.id in excluded_ids for feature in self.features):
            raise ValueError("excluded feature appears in catalog")
        for feature in self.features:
            for option in feature.options:
                if (
                    option.status not in VALID_STATUSES
                    or option.weight <= 0
                    or not math.isfinite(option.weight)
                ):
                    raise ValueError(f"invalid option metadata: {feature.id}.{option.id}")
                if not self._reachable(feature.id, option.id):
                    raise ValueError(f"unreachable option: {feature.id}.{option.id}")
        return True

    def _reachable(self, target_id, target_option):
        return self._find({target_id: target_option}, 0, {}) is not None

    def _find(self, fixed, index, assignment):
        if index == len(self.features):
            return assignment if not self._violations(assignment) else None
        feature = self.features[index]
        if not self._active(feature, assignment):
            if feature.id in fixed:
                return None
            assignment[feature.id] = None
            result = self._find(fixed, index + 1, assignment)
            assignment.pop(feature.id)
            return result
        choices = [o.id for o in feature.options]
        if feature.id in fixed:
            choices = [fixed[feature.id]]
        for value in choices:
            assignment[feature.id] = value
            if not self._violations(assignment, partial=True):
                result = self._find(fixed, index + 1, assignment)
                if result is not None:
                    assignment.pop(feature.id)
                    return result
        assignment.pop(feature.id, None)
        return None

    def sample(self, seed, fixed=None, uniform=False):
        fixed = dict(fixed or {})
        for fid, value in fixed.items():
            feature = next((f for f in self.features if f.id == fid), None)
            if feature is None or value not in {o.id for o in feature.options}:
                raise ValueError(f"unknown fixed feature option: {fid}={value}")
        assignment: dict[str, str | None] = {}
        violations = set()

        def visit(index):
            if index == len(self.features):
                return dict(assignment) if not self._violations(assignment) else None
            feature = self.features[index]
            if not self._active(feature, assignment):
                if feature.id in fixed:
                    violations.add(f"applies_if:{feature.id}")
                    return None
                assignment[feature.id] = None
                result = visit(index + 1)
                assignment.pop(feature.id)
                return result
            options = [
                o for o in feature.options if feature.id not in fixed or o.id == fixed[feature.id]
            ]
            rng = item_rng(seed, self.language_id, self.output_version, "feature", feature.id)
            pool = list(options)
            while pool:
                weights = [1.0 if uniform else o.weight for o in pool]
                choice = rng.choices(pool, weights=weights, k=1)[0]
                pool.remove(choice)
                assignment[feature.id] = choice.id
                found = visit(index + 1) if not self._violations(assignment, partial=True) else None
                if found is not None:
                    assignment.pop(feature.id, None)
                    return found
                violations.update(self._violations(assignment, partial=True))
            assignment.pop(feature.id, None)
            return None

        result = visit(0)
        if result is None:
            raise IncompatibleFeatures(violations or [c.id for c in self.constraints])
        return result

    def describe_features(self):
        lines = []
        for feature in self.features:
            fields = ", ".join(feature.source_fields) or "none"
            lines.append(f"{feature.id} [{feature.group}] source_fields={fields}")
            for option in feature.options:
                attestation = ", ".join(option.attested_in) or "none stated"
                lines.append(
                    f"  {option.id}: weight={option.weight:g}; {option.status}; attested_in={attestation}"
                    + (f"; {option.note}" if option.note else "")
                )
        if self.excluded_features:
            lines.append("Excluded features:")
            lines.extend(f"  {fid}: {reason}" for fid, reason in self.excluded_features)
        if self.constraints:
            lines.append("Constraints:")
            for constraint in self.constraints:
                lines.append(
                    f"  {constraint.id}: {dict(constraint.if_)} -> {dict(constraint.then)}; "
                    f"reason={constraint.reason}; {constraint.justification}"
                )
        return "\n".join(lines)
