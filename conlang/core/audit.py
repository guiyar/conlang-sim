"""Track intermediate-representation field paths read during realization."""

from dataclasses import fields, is_dataclass
from .ir import STRUCTURAL_FIELDS


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
        self.read_paths = set()
        self.value = _wrap(ir, "", self.read_paths)

    def passes(self, allowed_fields):
        allowed = set(allowed_fields)
        for path in self.read_paths:
            if any(other.startswith(path + ".") or other.startswith(path + "[]") for other in self.read_paths if other != path):
                continue
            if path in STRUCTURAL_FIELDS:
                continue
            normalized = path.replace("clause.arguments[].np.", "np.")
            normalized = normalized.replace("clause.arguments[].", "argument.")
            normalized = normalized.replace("np.kind", "np.head.kind")
            normalized = normalized.replace("np.person", "np.pronoun.person")
            normalized = normalized.replace("np.gender", "np.pronoun.gender")
            normalized = normalized.replace("np.case", "np.pronoun.case")
            if normalized in STRUCTURAL_FIELDS:
                continue
            if not any(normalized == field or normalized.startswith(field + ".") or normalized.startswith(field + "[") for field in allowed):
                return False
        return True