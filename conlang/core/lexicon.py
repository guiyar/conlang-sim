"""Stable per-instance lexical root generation."""

import random
from collections.abc import Iterable, Mapping
from typing import Callable, Protocol, TypedDict

from .seeds import item_rng


class LexiconPhonology(Protocol):
    def make_root(self, rng: random.Random, lemma: str, pos: str, shape: str) -> str: ...

    def make_syllable(self, rng: random.Random, shape: str) -> str: ...


class LexiconEntry(TypedDict):
    form: str
    gloss: str
    lemma: str | None
    pos: str | None
    category: str


class Lexicon:
    def __init__(
        self,
        seed: int | str,
        language_id: str,
        output_version: int,
        phonology: LexiconPhonology,
        shape_for_pos: Callable[[str], str] | None = None,
        closed_forms: Mapping[tuple[str, str], str] | None = None,
        gloss_for: Callable[[str, str], str] | None = None,
        canonical_key: Callable[[str, str], tuple[str, str]] | None = None,
    ):
        self.seed = seed
        self.language_id = language_id
        self.output_version = output_version
        self.phonology = phonology
        self.shape_for_pos = shape_for_pos or (lambda pos: "numeral" if pos == "NUM" else "content")
        self.entries: dict[tuple[str, str], str] = {}
        self.function_forms: set[str] = set()
        self.closed_forms = dict(closed_forms or {})
        self._export_entries: dict[tuple[str, str, str], LexiconEntry] = {}
        self._gloss_for = gloss_for or (lambda lemma, pos: lemma.upper())
        self._canonical_key = canonical_key or (lambda lemma, pos: (lemma, pos))

    def register_function_forms(self, forms: Mapping[object, str] | Iterable[str]) -> None:
        self.function_forms.update(forms.values() if isinstance(forms, Mapping) else forms)

    def register_closed_forms(self, forms: Mapping[tuple[str, str], str]) -> None:
        self.closed_forms.update(forms)

    def record(
        self,
        form: str,
        gloss: str,
        lemma: str | None = None,
        pos: str | None = None,
        category: str = "function",
    ) -> None:
        entry: LexiconEntry = {
            "form": form,
            "gloss": gloss,
            "lemma": lemma,
            "pos": pos,
            "category": category,
        }
        self._export_entries[(category, gloss, form)] = entry

    def literal(self, form: str, gloss: str | None = None) -> str:
        self.record(form, form if gloss is None else gloss, category="literal")
        return form

    def gloss(self, lemma: str, pos: str) -> str:
        return self._gloss_for(lemma, pos)

    def root(self, lemma: str, pos: str) -> str:
        lemma, pos = self._canonical_key(lemma, pos)
        key = (lemma, pos)
        if key in self.closed_forms:
            form = self.closed_forms[key]
            self.record(form, self.gloss(lemma, pos), lemma, pos, "function")
            return form
        shape = self.shape_for_pos(pos)
        function_word = shape == "function"
        if not function_word and key in self.entries:
            return self.entries[key]
        stream = "fn" if function_word else "lex"
        form = self._mint(lemma, pos, stream, shape)
        if function_word:
            self.closed_forms[key] = form
        else:
            self.entries[key] = form
        self.record(
            form, self.gloss(lemma, pos), lemma, pos, "function" if function_word else "lexical"
        )
        return form

    def _mint(self, lemma: str, pos: str, stream: str, shape: str) -> str:
        """A form depends only on the item and the pre-minted function set, never on call order."""
        for attempt in range(64):
            key_part = f"{lemma}/{pos}" if attempt == 0 else f"{lemma}/{pos}:retry:{attempt}"
            rng = item_rng(self.seed, self.language_id, self.output_version, stream, key_part)
            form = self.phonology.make_root(rng, lemma, pos, shape=shape)
            if form not in self.function_forms:
                return form
        fallback = item_rng(
            self.seed, self.language_id, self.output_version, stream, f"{lemma}/{pos}:fallback"
        )
        return self.phonology.make_root(
            fallback, lemma, pos, shape=shape
        ) + self.phonology.make_syllable(fallback, shape="function")

    def export(self) -> list[LexiconEntry]:
        return [self._export_entries[key] for key in sorted(self._export_entries)]

    def collisions(self) -> dict[str, list[str]]:
        reverse: dict[str, list[str]] = {}
        for (lemma, pos), form in sorted(self.entries.items()):
            reverse.setdefault(form, []).append(f"{lemma}/{pos}")
        return {form: keys for form, keys in reverse.items() if len(keys) > 1}
