import io

import pytest

from conlang.cli import main
from conlang.core.base import Translator
from conlang.core.registry import discover_languages
from conlang.core.results import is_info

PROFILE = discover_languages()["austronesian"]
VERBLESS = (
    "the cat",
    "a cat",
    "three dogs",
    "one hundred and one dogs",
    "one cat, two cats, three cats",
    "Hello!",
    "the cat in the house",
)
CHATTY = "Alice left and Bob ran tomorrow."


def test_no_rule_string_repeats_within_a_result():
    battery = (
        *VERBLESS,
        CHATTY,
        "I saw one hundred and one dogs.",
        "!!!",
        "very quickly",
        "Birds fly.",
    )
    for seed in range(10):
        translator = Translator(PROFILE, str(seed))
        for text in battery:
            for result in translator.translate(text, check=True):
                assert len(result.rules) == len(set(result.rules)), (seed, text, result.rules)


def test_valid_verbless_input_emits_no_root_missing_notice():
    translator = Translator(PROFILE, "2026")
    for text in VERBLESS:
        for result in translator.translate(text):
            assert not [r for r in result.rules if "No verbal" in r], (text, result.rules)
            assert not result.fallback_spans


@pytest.mark.parametrize("text", ("!!!", "very quickly"))
def test_true_rootless_fallback_keeps_its_notices_unfolded(text):
    result = Translator(PROFILE, "2026").translate(text)[0]
    assert "No verbal or be root found; source tokens use conlang lexical fallback." in result.rules
    assert "No verbal root; token-by-token conlang fallback used." in result.rules
    assert not any(is_info(rule) for rule in result.rules)


def test_embedded_clause_and_residual_notes_are_info_level():
    result = Translator(PROFILE, "7").translate(CHATTY)[0]
    info = [rule for rule in result.rules if is_info(rule)]
    assert any(rule.startswith("Embedded and coordinated clauses") for rule in info)
    assert "residual token: tomorrow" in info


def test_info_is_hidden_by_default_and_shown_with_verbose(capsys):
    assert main(["--seed", "7", CHATTY]) == 0
    quiet = capsys.readouterr()
    assert main(["--seed", "7", "--verbose", CHATTY]) == 0
    loud = capsys.readouterr()
    assert "[rule]" not in quiet.err
    assert "Embedded and coordinated" in loud.err and "residual token: tomorrow" in loud.err
    assert quiet.out == loud.out


def test_notices_are_shown_by_default(capsys):
    main(["--seed", "7", "!!!"])
    assert "[rule] No verbal root; token-by-token conlang fallback used." in capsys.readouterr().err


def test_check_output_is_unchanged(capsys):
    assert main(["--seed", "7", "--check", "the cat"]) == 0
    captured = capsys.readouterr()
    assert "IR audit: passed" in captured.out
    assert "Lexical collisions: {}" in captured.out
    assert "[rule] IR audit passed." in captured.err


def test_repl_rules_command_toggles_info_output(monkeypatch, capsys):
    script = f"{CHATTY}\n:rules\n{CHATTY}\n:rules\n{CHATTY}\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(script))
    assert main(["--seed", "7", "--repl"]) == 0
    first, rest = capsys.readouterr().err.split("rules on", 1)
    shown, last = rest.split("rules off", 1)
    assert "Embedded and coordinated" not in first
    assert "Embedded and coordinated" in shown
    assert "Embedded and coordinated" not in last
