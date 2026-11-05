import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from conlang.core import registry
from conlang.languages.austronesian.catalog import CATALOG


ROOT = Path(__file__).resolve().parents[2]


def test_architecture_core_has_no_profile_imports_and_only_parser_imports_spacy():
    core = ROOT / "conlang" / "core"
    spacy_imports = []
    profile_imports = []
    for path in core.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "spacy" or name.startswith("spacy.") for name in names):
                spacy_imports.append(path.name)
            if any(name.startswith("conlang.languages") for name in names):
                profile_imports.append(path.name)
    assert spacy_imports == ["parser.py"]
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
    profile = SimpleNamespace(
        language_id="duplicate_test", output_version=2, catalog=CATALOG,
        phonology=lambda *args: None, realize=lambda *args: None, describe=lambda *args: "",
    )
    monkeypatch.setitem(registry.LANGUAGES, "duplicate_test", profile)
    with pytest.raises(ValueError, match="duplicate language ID"):
        registry.register_language(profile)

    class InvalidCatalog:
        @staticmethod
        def validate_catalog():
            raise ValueError("bad catalog")

    invalid = SimpleNamespace(
        language_id="invalid_test", output_version=1, catalog=InvalidCatalog(),
        phonology=lambda *args: None, realize=lambda *args: None, describe=lambda *args: "",
    )
    with pytest.raises(ValueError, match="bad catalog"):
        registry.register_language(invalid)


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
    monkeypatch.setattr(registry.pkgutil, "iter_modules", lambda path: [
        SimpleNamespace(name="_hidden"), SimpleNamespace(name="broken"),
    ])
    registry.PLUGIN_FAILURES.pop("broken", None)
    registry.discover_languages()
    assert "conlang.languages._hidden.profile" not in imports
    assert registry.PLUGIN_FAILURES["broken"] == "RuntimeError: broken plugin"
    registry.PLUGIN_FAILURES.pop("broken", None)