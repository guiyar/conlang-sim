"""Language profile registration and deterministic plugin discovery."""

import importlib
import pkgutil
import re
from collections.abc import Callable, Iterable
from typing import Protocol

from .features import FeatureCatalog


class LanguageProfile(Protocol):
    language_id: str
    name: str
    description: str
    output_version: int
    catalog: FeatureCatalog
    phonology_class: Callable[..., object]
    realizer_class: Callable[..., object]

    def phonology(self, features, seed, language_id, output_version): ...

    def realize(self, ir, translator): ...

    def describe(self, features, parameters, phonology=None, function_morphs=None): ...


class LanguageRegistry:
    def __init__(self):
        self.profiles: dict[str, LanguageProfile] = {}
        self.discovery_failures: dict[str, str] = {}

    def register(self, profile: LanguageProfile) -> LanguageProfile:
        language_id = getattr(profile, "language_id", None)
        if not isinstance(language_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", language_id):
            raise ValueError(f"invalid language ID: {language_id!r}")
        for name in ("name", "description", "catalog", "phonology_class", "realizer_class"):
            if not hasattr(profile, name):
                raise TypeError(f"language profile missing {name}")
        for name in ("phonology", "realize", "describe"):
            if not callable(getattr(profile, name, None)):
                raise TypeError(f"language profile {name} must be callable")
        if not isinstance(profile.output_version, int) or isinstance(profile.output_version, bool):
            raise TypeError("output_version must be an integer")
        for name in ("phonology_class", "realizer_class"):
            if not callable(getattr(profile, name)):
                raise TypeError(f"language profile {name} must be callable")
        validate_catalog = getattr(profile.catalog, "validate_catalog", None)
        if not callable(validate_catalog):
            raise TypeError("language profile catalog must provide validate_catalog")
        validate_catalog()
        if language_id in self.profiles:
            raise ValueError(f"duplicate language ID: {language_id}")
        self.profiles[language_id] = profile
        return profile

    def get(self, language_id):
        return self.profiles.get(language_id)

    def available(self):
        return tuple(sorted(self.profiles))

    def discover(self, package_name="conlang.languages"):
        package = importlib.import_module(package_name)
        for module_info in sorted(
            pkgutil.iter_modules(package.__path__), key=lambda entry: entry.name
        ):
            if module_info.name.startswith("_"):
                continue
            try:
                module = importlib.import_module(f"{package_name}.{module_info.name}.profile")
                self.discovery_failures.pop(module_info.name, None)
                for profile in _profiles_in(module):
                    language_id = getattr(profile, "language_id", None)
                    if isinstance(language_id, str) and self.profiles.get(language_id) is profile:
                        continue
                    self.register(profile)
            except Exception as error:
                self.discovery_failures[module_info.name] = f"{type(error).__name__}: {error}"
        return dict(sorted(self.profiles.items()))


def _profiles_in(module) -> Iterable[LanguageProfile]:
    for candidate in vars(module).values():
        if getattr(candidate, "__module__", None) == module.__name__ and hasattr(
            candidate, "language_id"
        ):
            yield candidate


DEFAULT_REGISTRY = LanguageRegistry()
LANGUAGES = DEFAULT_REGISTRY.profiles
PLUGIN_FAILURES = DEFAULT_REGISTRY.discovery_failures


def register_language(profile, registry=DEFAULT_REGISTRY):
    return registry.register(profile)


def discover_languages(registry=DEFAULT_REGISTRY):
    return registry.discover()
