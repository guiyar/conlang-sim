"""Stable per-instance lexical root generation."""

from .seeds import item_rng


class Lexicon:
    def __init__(self, seed, language_id, output_version, phonology):
        self.seed = seed
        self.language_id = language_id
        self.output_version = output_version
        self.phonology = phonology
        self.entries = {}
        self.function_forms = set()

    def register_function_forms(self, forms):
        self.function_forms.update(forms)

    def root(self, lemma, pos):
        key = (lemma, pos)
        if key in self.entries:
            return self.entries[key]
        forbidden = self.function_forms
        for attempt in range(64):
            rng = item_rng(self.seed, self.language_id, self.output_version, "lex", f"{lemma}/{pos}/{attempt}")
            form = self.phonology.make_root(rng, lemma, pos)
            if form not in forbidden:
                self.entries[key] = form
                return form
        rng = item_rng(self.seed, self.language_id, self.output_version, "lex", f"{lemma}/{pos}/fallback")
        form = self.phonology.make_root(rng, lemma, pos) + self.phonology.make_syllable(rng)
        self.entries[key] = form
        return form

    def collisions(self):
        reverse = {}
        for (lemma, pos), form in sorted(self.entries.items()):
            reverse.setdefault(form, []).append(f"{lemma}/{pos}")
        return {form: keys for form, keys in reverse.items() if len(keys) > 1}