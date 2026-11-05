"""Track intermediate-representation field paths read during realization."""

from dataclasses import is_dataclass

from .ir import STRUCTURAL_FIELDS

_LINK_PREFIXES = ("clause.links[]", "np.post_modifiers[].link")


def _rebase_clause(path):
    """Rewrite paths inside a linked clause as if they were read from a top-level clause."""
    for prefix in _LINK_PREFIXES:
        if f"{prefix}.clause." in path:
            return "clause." + path.rsplit(f"{prefix}.clause.", 1)[1]
        if f"{prefix}.marker." in path:
            return "source_token." + path.rsplit(f"{prefix}.marker.", 1)[1]
        if path.endswith(f"{prefix}.marker"):
            return "clause_link.marker"
    return path


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
            normalized = _rebase_clause(path)
            normalized = normalized.replace(
                "clause.arguments[].np.source_tokens[].", "source_token."
            )
            normalized = normalized.replace("clause.arguments[].source_tokens[].", "source_token.")
            normalized = normalized.replace("clause.arguments[].np.", "np.")
            normalized = normalized.replace("np.post_modifiers[].np.", "np.")
            normalized = normalized.replace("np.coordinated[].np.", "np.")
            normalized = normalized.replace("np.coordinated[].conj.", "source_token.")
            normalized = normalized.replace("np.coordinated[].", "coordination.")
            normalized = normalized.replace("np.post_modifiers[].", "post_modifier.")
            normalized = normalized.replace("clause.adverbs[].", "modifier.")
            normalized = normalized.replace("clause.arguments[].", "argument.")
            normalized = normalized.replace("clause.source_tokens[].", "source_token.")
            normalized = normalized.replace("np.source_tokens[].", "source_token.")
            normalized = normalized.replace("source_tokens[].", "source_token.")
            normalized = normalized.replace("np.kind", "np.head.kind")
            normalized = normalized.replace("np.person", "np.pronoun.person")
            normalized = normalized.replace("np.gender", "np.pronoun.gender")
            normalized = normalized.replace("np.case", "np.pronoun.case")
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
