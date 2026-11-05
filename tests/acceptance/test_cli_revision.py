import json

import pytest

from conlang.cli import main


def test_G1_set_flags_and_constraint_errors(capsys):
    assert (
        main(
            [
                "--uniform",
                "--set",
                "alignment=plain",
                "--set",
                "case_particles=none",
                "--seed",
                "5",
                "The dog ran.",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert output.strip()
    with pytest.raises(SystemExit) as error:
        main(["--set", "alignment=plain", "--set", "case_particles=preposed"])
    assert error.value.code != 0
    assert "plain_has_no_case_particles" in capsys.readouterr().err


def test_G1_unknown_option_shows_valid_feature_choices(capsys):
    with pytest.raises(SystemExit):
        main(["--set", "vowels=invalid"])
    error = capsys.readouterr().err
    assert "v3" in error and "v5" in error


def test_G2_describe_is_readable_and_includes_required_dialect_fields(capsys):
    main(["--seed", "4", "--describe"])
    output = capsys.readouterr().out
    for label in (
        "Vowels:",
        "Consonants:",
        "Syllable template:",
        "Codas:",
        "Word order:",
        "Alignment:",
        "Article system:",
        "TAM system:",
        "Function morphs:",
    ):
        assert label in output
    assert "{" not in output


def test_G3_export_contains_seed_and_function_morphs(capsys):
    main(["--seed", "12", "--export-dialect"])
    exported = json.loads(capsys.readouterr().out)
    assert exported["seed"] == "12"
    assert exported["output_version"] == 3
    assert isinstance(exported["function_morphs"], dict)
    assert "parser_versions" in exported


def test_G4_lexicon_flag_outputs_the_export_schema(capsys):
    main(["--seed", "12", "--lexicon", "Mina saw 42 birds."])
    output = capsys.readouterr().out
    entries = json.loads(output[output.rfind("[") :])
    assert {"form", "gloss", "lemma", "pos", "category"} == set(entries[0])
    assert {entry["form"] for entry in entries if entry["category"] == "literal"} >= {"Mina", "42"}


def test_G5_features_show_weights_and_new_article_features(capsys):
    main(["--features"])
    output = capsys.readouterr().out
    assert "articles" in output and "article_position" in output
    assert "weight=0.7" in output
    assert "plain_has_no_case_particles" in output


def test_G6_glossed_multisentence_output_has_blank_line_between_blocks(capsys):
    main(["--gloss", "Alice left. Bob ran."])
    output = capsys.readouterr().out
    assert "\n\n" in output


def test_G_check_accepts_all_realization_field_reads(capsys):
    main(["--check", "The child saw two birds in the garden."])
    assert "IR audit: passed" in capsys.readouterr().out


def test_repl_matches_one_shot_and_survives_errors(monkeypatch, capsys):
    import io

    from conlang.core import base

    main(["--seed", "7", "The dog ran."])
    expected = capsys.readouterr().out
    real = base.Translator.translate

    def flaky(self, text, check=False):
        if text == "boom":
            raise RuntimeError("bad parse")
        return real(self, text, check=check)

    monkeypatch.setattr(base.Translator, "translate", flaky)
    monkeypatch.setattr("sys.stdin", io.StringIO("boom\nThe dog ran.\n:seed 8\n:quit\n"))
    assert main(["--seed", "7", "--repl"]) == 0
    captured = capsys.readouterr()
    assert captured.out == expected
    assert "error: bad parse" in captured.err
