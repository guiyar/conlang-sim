"""Command-line interface for seeded conlang generation."""

import argparse
import json
import sys
from conlang.core.base import Translator
from conlang.core.parser import parser_versions
from conlang.core.registry import PLUGIN_FAILURES, discover_languages
from conlang.core.render import render


def main(argv=None):
    parser = argparse.ArgumentParser(prog="conlang")
    parser.add_argument("sentence", nargs="*")
    parser.add_argument("--language", default="austronesian")
    parser.add_argument("--seed", default="0")
    parser.add_argument("--gloss", action="store_true")
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--features", action="store_true")
    parser.add_argument("--lexicon", action="store_true")
    parser.add_argument("--export-dialect", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--list-languages", action="store_true")
    args = parser.parse_args(argv)
    languages = discover_languages()
    if args.list_languages:
        for language_id, profile in languages.items():
            print(f"{language_id}: {profile.name}")
        for language_id, error in sorted(PLUGIN_FAILURES.items()):
            print(f"{language_id}: FAILED: {error}")
        return 0
    if args.language not in languages:
        if args.language in PLUGIN_FAILURES:
            parser.error(f"language {args.language} failed to load: {PLUGIN_FAILURES[args.language]}")
        parser.error(f"unknown language {args.language!r}; use --list-languages")
    profile = languages[args.language]
    translator = Translator(profile, args.seed)
    if args.features:
        print(profile.catalog.describe_features())
    if args.describe:
        print(profile.describe(translator.features, translator.phonology.parameters))
    if args.export_dialect:
        exported = {"language_id": profile.language_id, "output_version": profile.output_version,
                    "features": translator.features, "parameters": translator.phonology.parameters,
                    "parser_versions": parser_versions()}
        print(json.dumps(exported, sort_keys=True, indent=2))
    if args.sentence:
        source = " ".join(args.sentence)
        result = translator.translate(source, check=args.check)
        print(render(result.words, gloss=args.gloss))
        for rule in result.rules:
            print(f"[rule] {rule}", file=sys.stderr)
    if args.lexicon:
        entries = [{"lemma": lemma, "pos": pos, "form": form} for (lemma, pos), form in sorted(translator.lexicon.entries.items())]
        print(json.dumps(entries, sort_keys=True, indent=2))
    if args.check:
        collisions = translator.lexicon.collisions()
        audit_rules = result.rules if args.sentence else []
        audit_result = "passed" if "IR audit passed." in audit_rules else "failed" if audit_rules else "not run"
        print("IR audit: " + audit_result)
        print("Lexical collisions: " + json.dumps(collisions, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())