import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from conlang.core import registry
from conlang.languages.austronesian.catalog import CATALOG

ROOT = Path(__file__).resolve().parents[2]


def _profile(language_id, catalog=CATALOG):
    return SimpleNamespace(
        language_id=language_id,
        name=language_id,
        description="test profile",
        output_version=1,
        catalog=catalog,
        phonology_class=lambda *args: None,
        realizer_class=lambda *args: None,
        phonology=lambda *args: None,
        realize=lambda *args: None,
        describe=lambda *args: "",
    )


def test_architecture_core_has_no_profile_imports_and_only_english_parser_imports_spacy():
    core = ROOT / "conlang" / "core"
    spacy_imports = []
    profile_imports = []
    for path in core.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "spacy" or name.startswith("spacy.") for name in names):
                spacy_imports.append(path.relative_to(core).as_posix())
            if any(name.startswith("conlang.languages") for name in names):
                profile_imports.append(path.relative_to(core).as_posix())
    assert spacy_imports == ["parsing/english.py"]
    assert profile_imports == []


def test_template_package_is_working_but_not_discovered():
    from conlang.languages._template.catalog import CATALOG as template_catalog
    from conlang.languages._template.grammar import TemplateRealizer
    from conlang.languages._template.phonology import TemplatePhonology
    from conlang.languages._template.profile import TemplateProfile

    assert template_catalog.validate_catalog()
    assert TemplateRealizer and TemplatePhonology
    assert TemplateProfile.catalog is template_catalog
    assert "_template" not in registry.discover_languages()


def test_registry_rejects_duplicate_ids_and_invalid_catalogs(monkeypatch):
    profile = _profile("duplicate_test")
    profile.output_version = 2
    monkeypatch.setitem(registry.LANGUAGES, "duplicate_test", profile)
    with pytest.raises(ValueError, match="duplicate language ID"):
        registry.register_language(profile)

    class InvalidCatalog:
        @staticmethod
        def validate_catalog():
            raise ValueError("bad catalog")

    invalid = _profile("invalid_test", InvalidCatalog())
    with pytest.raises(ValueError, match="bad catalog"):
        registry.register_language(invalid)


def test_language_registries_are_independent_and_validate_profile_callables():
    first = registry.LanguageRegistry()
    second = registry.LanguageRegistry()
    profile = _profile("isolated_test")

    first.register(profile)

    assert first.get("isolated_test") is profile
    assert first.available() == ("isolated_test",)
    assert second.available() == ()
    assert "isolated_test" not in registry.LANGUAGES

    discovered = second.discover()

    assert "austronesian" in discovered
    assert "austronesian" not in first.profiles

    malformed = _profile("malformed_test")
    malformed.realize = None
    with pytest.raises(TypeError, match="realize must be callable"):
        second.register(malformed)


def test_discovery_skips_underscores_and_reports_broken_plugins(monkeypatch):
    package = registry.importlib.import_module("conlang.languages")
    original_import = registry.importlib.import_module
    imports = []

    def fake_import(name):
        imports.append(name)
        if name == "conlang.languages":
            return package
        if name == "conlang.languages.broken.profile":
            raise RuntimeError("broken plugin")
        return original_import(name)

    monkeypatch.setattr(registry.importlib, "import_module", fake_import)
    monkeypatch.setattr(
        registry.pkgutil,
        "iter_modules",
        lambda path: [
            SimpleNamespace(name="_hidden"),
            SimpleNamespace(name="broken"),
        ],
    )
    registry.PLUGIN_FAILURES.pop("broken", None)
    registry.discover_languages()
    assert "conlang.languages._hidden.profile" not in imports
    assert registry.PLUGIN_FAILURES["broken"] == "RuntimeError: broken plugin"
    registry.PLUGIN_FAILURES.pop("broken", None)
