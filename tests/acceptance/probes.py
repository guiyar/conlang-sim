"""Shared probe sentences and dialect matrix for the correctness-probe tests."""

import copy
import itertools
import random
from functools import lru_cache

from conlang.core.base import Translator
from conlang.core.features import IncompatibleFeatures
from conlang.core.parser import parse
from conlang.core.registry import discover_languages

PROFILE = discover_languages()["austronesian"]

PROBES = (
    "I was born in 2026.",
    "It costs $5.",
    "The cat ate at 3:30.",
    "I saw 2 cats and 1,000 dogs.",
    "All the dogs ate.",
    "Why is the cat here?",
    "Eat the dog!",
    "Thank you.",
    "She gave him the dog.",
    "The cat has eaten the dog.",
    "The cat can eat the dog.",
    "This dog is bigger than that cat.",
    "The cat is the biggest.",
    "I want to eat.",
    "The cat very quickly ate the dog.",
    "THE CAT ATE THE DOG",
    "Mary and John saw New York.",
    "Come here!",
    "The cat in the house sleeps.",
    "The dog that the cat saw is big.",
)

OPTIONS = {
    "articles": ("none", "both", "definite_only", "indefinite_only"),
    "article_position": ("before", "after"),
    "noun_number": ("none", "particle", "full_reduplication", "partial_reduplication"),
    "modifier_position": ("after", "before"),
    "linker": ("none", "particle"),
    "alignment": ("symmetrical_voice", "active_passive", "ergative", "plain"),
    "clause_order": ("VSO", "VOS", "SVO", "SOV"),
    "case_particles": ("none", "preposed"),
    "tam_system": ("tense3", "past_nonpast", "aspect3"),
    "tam_exponence": ("particle", "affix"),
    "question": ("particle_initial", "particle_final", "none"),
    "pronoun_strategy": ("free", "clitic_second", "clitic_verb"),
}


def _valid(candidate):
    if (candidate["articles"] == "none") == ("article_position" in candidate):
        return False
    if (candidate["modifier_position"] == "before") == ("linker" in candidate):
        return False
    case = candidate["case_particles"]
    align = candidate["alignment"]
    return not (
        (align in {"symmetrical_voice", "ergative"} and case != "preposed")
        or (align == "plain" and case != "none")
    )


def _random_candidate(rng):
    candidate = {name: rng.choice(options) for name, options in OPTIONS.items()}
    if candidate["articles"] == "none":
        del candidate["article_position"]
    if candidate["modifier_position"] == "before":
        del candidate["linker"]
    return candidate


def _pairs(candidate):
    return set(itertools.combinations(sorted(candidate.items()), 2))


def _build_matrix():
    rng = random.Random(0)
    pool = []
    while len(pool) < 1500:
        candidate = _random_candidate(rng)
        if _valid(candidate):
            pool.append(candidate)
    uncovered = set().union(*(_pairs(c) for c in pool))
    chosen = []
    while uncovered:
        best = max(pool, key=lambda c: len(_pairs(c) & uncovered))
        chosen.append(best)
        uncovered -= _pairs(best)
    return chosen


MATRIX = _build_matrix()


def label(fixed):
    return "-".join(f"{k}={v}" for k, v in sorted(fixed.items()))


def make_translator(fixed, seed="7"):
    return Translator(PROFILE, seed, fixed=fixed)


def dialect_translators():
    """Fresh translators for every matrix dialect that the catalog accepts."""
    for fixed in MATRIX:
        try:
            yield label(fixed), make_translator(fixed)
        except IncompatibleFeatures:
            continue


@lru_cache(maxsize=None)
def _parsed(text):
    return parse(text)


def fresh(text):
    return copy.deepcopy(_parsed(text))


def morphemes(words):
    return [m for w in words for m in w.morphemes]


def glosses(words):
    return [m.gloss for m in morphemes(words)]
