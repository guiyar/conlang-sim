"""Stable per-instance lexical root generation."""

from .seeds import item_rng


class Lexicon:
    def __init__(
        self, seed, language_id, output_version, phonology, shape_for_pos=None, closed_forms=None
    ):
        self.seed = seed
        self.language_id = language_id
        self.output_version = output_version
        self.phonology = phonology
        self.shape_for_pos = shape_for_pos or (lambda pos: "numeral" if pos == "NUM" else "content")
        self.entries = {}
        self.function_forms = set()
        self.closed_forms = dict(closed_forms or {})
        self._export_entries = {}

    def register_function_forms(self, forms):
        self.function_forms.update(forms.values() if isinstance(forms, dict) else forms)

    def register_closed_forms(self, forms):
        self.closed_forms.update(forms)

    def record(self, form, gloss, lemma=None, pos=None, category="function"):
        entry = {"form": form, "gloss": gloss, "lemma": lemma, "pos": pos, "category": category}
        self._export_entries[(category, gloss, form)] = entry

    def literal(self, form, gloss=None):
        self.record(form, form if gloss is None else gloss, category="literal")
        return form

    def root(self, lemma, pos):
        key = (lemma, pos)
        if key in self.closed_forms:
            form = self.closed_forms[key]
            self.record(form, lemma.upper(), lemma, pos, "function")
            return form
        shape = self.shape_for_pos(pos)
        if shape == "function":
            for attempt in range(64):
                key_part = f"{lemma}/{pos}" if attempt == 0 else f"{lemma}/{pos}:retry:{attempt}"
                rng = item_rng(self.seed, self.language_id, self.output_version, "fn", key_part)
                form = self.phonology.make_root(rng, lemma, pos, shape="function")
                if form not in self.function_forms and form not in self.entries.values():
                    self.closed_forms[key] = form
                    self.function_forms.add(form)
                    self.record(form, lemma.upper(), lemma, pos, "function")
                    return form
            fallback = item_rng(
                self.seed, self.language_id, self.output_version, "fn", f"{lemma}/{pos}:fallback"
            )
            form = self.phonology.make_root(
                fallback, lemma, pos, shape="function"
            ) + self.phonology.make_syllable(fallback, shape="function")
            self.closed_forms[key] = form
            self.function_forms.add(form)
            self.record(form, lemma.upper(), lemma, pos, "function")
            return form
        if key in self.entries:
            return self.entries[key]
        forbidden = self.function_forms | set(self.entries.values())
        for attempt in range(64):
            key_part = f"{lemma}/{pos}" if attempt == 0 else f"{lemma}/{pos}:retry:{attempt}"
            rng = item_rng(self.seed, self.language_id, self.output_version, "lex", key_part)
            form = self.phonology.make_root(rng, lemma, pos, shape=shape)
            if form not in forbidden:
                self.entries[key] = form
                self.record(form, lemma.upper(), lemma, pos, "lexical")
                return form
        fallback = item_rng(
            self.seed, self.language_id, self.output_version, "lex", f"{lemma}/{pos}:fallback"
        )
        form = self.phonology.make_root(
            fallback, lemma, pos, shape=shape
        ) + self.phonology.make_syllable(fallback, shape="function")
        self.entries[key] = form
        self.record(form, lemma.upper(), lemma, pos, "lexical")
        return form

    def export(self):
        return [self._export_entries[key] for key in sorted(self._export_entries)]

    def collisions(self):
        reverse: dict[str, list[str]] = {}
        for (lemma, pos), form in sorted(self.entries.items()):
            reverse.setdefault(form, []).append(f"{lemma}/{pos}")
        return {form: keys for form, keys in reverse.items() if len(keys) > 1}
