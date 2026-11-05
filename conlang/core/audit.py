"""Track intermediate-representation field paths read during realization."""

import re
from dataclasses import dataclass, is_dataclass

from .ir import STRUCTURAL_FIELDS


@dataclass(frozen=True)
class _FieldPath:
    parts: tuple[str, ...]

    @classmethod
    def parse(cls, path):
        parts = re.findall(r"[^.\[\]]+|\[\d*\]", path)
        return cls(tuple("[]" if part.startswith("[") else part for part in parts))

    def starts_with(self, prefix):
        return self.parts[: len(prefix)] == prefix

    def replace_prefix(self, prefix, replacement):
        return _FieldPath(replacement + self.parts[len(prefix) :])

    def __str__(self):
        path = ""
        for part in self.parts:
            if part.startswith("["):
                path += part
            else:
                path += ("." if path else "") + part
        return path


@dataclass(frozen=True)
class _PathRule:
    prefix: tuple[str, ...]
    replacement: tuple[str, ...]


def _apply_rules(path, rules):
    for rule in rules:
        while path.starts_with(rule.prefix):
            path = path.replace_prefix(rule.prefix, rule.replacement)
    return path


_LINK_RULES = (
    _PathRule(("post_modifier", "link", "clause"), ("clause",)),
    _PathRule(("clause", "links", "[]", "clause"), ("clause",)),
    _PathRule(("np", "post_modifiers", "[]", "link", "clause"), ("clause",)),
    _PathRule(("clause", "links", "[]", "marker"), ("source_token",)),
    _PathRule(("np", "post_modifiers", "[]", "link", "marker"), ("source_token",)),
    _PathRule(("clause", "links", "[]"), ("clause_link",)),
    _PathRule(("np", "post_modifiers", "[]", "link"), ("clause_link",)),
    _PathRule(("post_modifier", "link"), ("clause_link",)),
)

_PATH_RULES = (
    _PathRule(("clause", "arguments", "[]", "np", "source_tokens", "[]"), ("source_token",)),
    _PathRule(("clause", "arguments", "[]", "source_tokens", "[]"), ("source_token",)),
    _PathRule(("clause", "arguments", "[]", "np"), ("np",)),
    _PathRule(("np", "post_modifiers", "[]", "np"), ("np",)),
    _PathRule(("np", "coordinated", "[]", "np"), ("np",)),
    _PathRule(("np", "coordinated", "[]", "conj"), ("source_token",)),
    _PathRule(("np", "coordinated", "[]"), ("coordination",)),
    _PathRule(("np", "post_modifiers", "[]"), ("post_modifier",)),
    _PathRule(("clause", "adverbs", "[]"), ("modifier",)),
    _PathRule(("np", "predeterminers", "[]"), ("modifier",)),
    _PathRule(("np", "adverbs", "[]"), ("modifier",)),
    _PathRule(("clause", "modals", "[]"), ("modifier",)),
    _PathRule(("modifier", "sub_modifiers", "[]"), ("modifier",)),
    _PathRule(("clause", "arguments", "[]"), ("argument",)),
    _PathRule(("clause", "source_tokens", "[]"), ("source_token",)),
    _PathRule(("np", "source_tokens", "[]"), ("source_token",)),
    _PathRule(("source_tokens", "[]"), ("source_token",)),
    _PathRule(("np", "kind"), ("np", "head", "kind")),
    _PathRule(("np", "person"), ("np", "pronoun", "person")),
    _PathRule(("np", "gender"), ("np", "pronoun", "gender")),
    _PathRule(("np", "case"), ("np", "pronoun", "case")),
)


def _normalize_path(path):
    field_path = _FieldPath.parse(path)
    marker_paths = {
        ("clause", "links", "[]", "marker"),
        ("np", "post_modifiers", "[]", "link", "marker"),
    }
    if field_path.parts in marker_paths:
        field_path = _FieldPath(("clause_link", "marker"))
    else:
        for _ in range(len(field_path.parts) + 1):
            previous = field_path
            field_path = _apply_rules(field_path, _PATH_RULES)
            marker_prefix = ("post_modifier", "link", "marker")
            if field_path.starts_with(marker_prefix):
                suffix = field_path.parts[len(marker_prefix) :]
                field_path = _FieldPath(
                    ("source_token",) + suffix if suffix else ("clause_link", "marker")
                )
            else:
                field_path = _apply_rules(field_path, _LINK_RULES)
            if field_path == previous:
                break
    return str(field_path)


class _Proxy:
    def __init__(self, value, path, reads):
        object.__setattr__(self, "_value", value)
        object.__setattr__(self, "_path", path)
        object.__setattr__(self, "_reads", reads)

    def __getattr__(self, name):
        value = object.__getattribute__(self, "_value")
        path = f"{object.__getattribute__(self, '_path')}.{name}" if self._path else name
        reads = object.__getattribute__(self, "_reads")
        reads.add(path)
        child = getattr(value, name)
        return _wrap(child, path, reads)

    def __setattr__(self, name, value):
        target = object.__getattribute__(self, "_value")
        setattr(target, name, value)

    def __iter__(self):
        return iter(_wrap(value, f"{self._path}[]", self._reads) for value in self._value)

    def __len__(self):
        return len(self._value)

    def __getitem__(self, index):
        path = f"{self._path}[{index}]"
        self._reads.add(path)
        return _wrap(self._value[index], path, self._reads)


def _wrap(value, path, reads):
    if is_dataclass(value):
        return _Proxy(value, path, reads)
    if isinstance(value, list):
        return [_wrap(item, f"{path}[]", reads) for item in value]
    if isinstance(value, dict):
        return value
    return value


class AuditedIR:
    def __init__(self, ir):
        self.read_paths: set[str] = set()
        self.value = _wrap(ir, "", self.read_paths)

    def passes(self, allowed_fields):
        allowed = set(allowed_fields)
        for path in self.read_paths:
            if any(
                other.startswith(path + ".") or other.startswith(path + "[]")
                for other in self.read_paths
                if other != path
            ):
                continue
            if path in STRUCTURAL_FIELDS:
                continue
            normalized = _normalize_path(path)
            if normalized in STRUCTURAL_FIELDS:
                continue
            if not any(
                normalized == field
                or normalized.startswith(field + ".")
                or normalized.startswith(field + "[")
                for field in allowed
            ):
                return False
        return True
