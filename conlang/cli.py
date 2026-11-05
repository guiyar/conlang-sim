"""Command-line interface for seeded conlang generation."""

import argparse
import json
import sys
from conlang.core.base import Translator
from conlang.core.features import IncompatibleFeatures
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
    parser.add_argument("--set", dest="fixed_features", action="append", default=[], metavar="FEATURE=OPTION")
    parser.add_argument("--uniform", action="store_true")
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
    feature_map = {feature.id: feature for feature in profile.catalog.features}
    fixed = {}
    for assignment in args.fixed_features:
        if "=" not in assignment:
            parser.error(f"--set expects FEATURE=OPTION, got {assignment!r}")
        feature_id, option_id = assignment.split("=", 1)
        feature = feature_map.get(feature_id)
        if feature is None:
            parser.error("unknown feature " + repr(feature_id) + "; valid features: " + ", ".join(feature_map))
        choices = [option.id for option in feature.options]
        if option_id not in choices:
            parser.error(f"unknown option {option_id!r} for {feature_id}; valid choices: {', '.join(choices)}")
        fixed[feature_id] = option_id
    try:
        translator = Translator(profile, args.seed, fixed=fixed, uniform=args.uniform)
    except IncompatibleFeatures as error:
        parser.error("incompatible feature assignment; violated constraints: " + ", ".join(error.constraint_ids))
    if args.features:
        print(profile.catalog.describe_features())
    if args.describe:
        print(profile.describe(
            translator.features, translator.phonology.parameters,
            phonology=translator.phonology, function_morphs=translator.function_morphs(),
        ))
    if args.export_dialect:
        exported = {"language_id": profile.language_id, "output_version": profile.output_version,
                    "features": translator.features, "parameters": translator.phonology.parameters,
                    "seed": args.seed, "function_morphs": translator.function_morphs(),
                    "parser_versions": parser_versions()}
        print(json.dumps(exported, sort_keys=True, indent=2))
    if args.sentence:
        source = " ".join(args.sentence)
        results = translator.translate(source, check=args.check)
        rendered = [render(result.words, gloss=args.gloss) for result in results]
        print(("\n\n" if args.gloss else "\n").join(rendered))
        for result in results:
            for rule in result.rules:
                print(f"[rule] {rule}", file=sys.stderr)
    if args.lexicon:
        print(json.dumps(translator.lexicon.export(), sort_keys=True, indent=2))
    if args.check:
        collisions = translator.lexicon.collisions()
        audit_rules = [rule for result in results for rule in result.rules] if args.sentence else []
        audit_result = "passed" if audit_rules and all("IR audit passed." in rule for rule in audit_rules if rule.startswith("IR audit")) and not any("IR audit failed" in rule for rule in audit_rules) else "failed" if any("IR audit failed" in rule for rule in audit_rules) else "not run"
        print("IR audit: " + audit_result)
        print("Lexical collisions: " + json.dumps(collisions, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())