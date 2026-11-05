"""Shared environment checks for parser-dependent tests."""

import importlib.metadata

import pytest

MODEL_INSTALL = "python -m spacy download en_core_web_sm-3.8.0"


def parser_model_problem():
    try:
        version = importlib.metadata.version("en-core-web-sm")
        spacy_version = importlib.metadata.version("spacy")
    except importlib.metadata.PackageNotFoundError:
        return f"Missing spaCy or en_core_web_sm 3.8.0. Install the model with: {MODEL_INSTALL}"
    if not version.startswith("3.8.0") or not spacy_version.startswith("3.8."):
        return f"Expected spaCy 3.8.x and en_core_web_sm 3.8.0, found spaCy {spacy_version} and model {version}. Reinstall with: {MODEL_INSTALL}"
    return None


PARSER_PROBLEM = parser_model_problem()


def pytest_report_header(config):
    return PARSER_PROBLEM


pytestmark = pytest.mark.skipif(
    PARSER_PROBLEM is not None, reason=PARSER_PROBLEM or "parser model available"
)


def pytest_addoption(parser):
    parser.addoption("--full-sweeps", action="store_true", help="run full-size seed sweeps")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--full-sweeps"):
        return
    skip = pytest.mark.skip(reason="stress test; pass --full-sweeps (make test-stress)")
    for item in items:
        if "stress" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def sweep(request):
    """Scale a seed count down to a tenth (min 10) unless --full-sweeps is given."""
    full = request.config.getoption("--full-sweeps")
    return lambda count: count if full else min(count, max(10, count // 10))
