"""Language profile registration and deterministic plugin discovery."""

import importlib
import pkgutil
import re

LANGUAGES = {}
PLUGIN_FAILURES = {}


def register_language(profile):
    language_id = getattr(profile, "language_id", None)
    if not isinstance(language_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", language_id):
        raise ValueError(f"invalid language ID: {language_id!r}")
    for name in ("output_version", "catalog", "phonology", "realize", "describe"):
        if not hasattr(profile, name):
            raise TypeError(f"language profile missing {name}")
    if not isinstance(profile.output_version, int):
        raise TypeError("output_version must be an integer")
    profile.catalog.validate_catalog()
    if language_id in LANGUAGES:
        raise ValueError(f"duplicate language ID: {language_id}")
    LANGUAGES[language_id] = profile
    return profile


def discover_languages():
    package = importlib.import_module("conlang.languages")
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda entry: entry.name):
        if info.name.startswith("_"):
            continue
        try:
            importlib.import_module(f"conlang.languages.{info.name}.profile")
        except Exception as error:
            PLUGIN_FAILURES[info.name] = f"{type(error).__name__}: {error}"
    return dict(sorted(LANGUAGES.items()))
