"""Translator instance owning its dialect and lexical state."""

from .audit import AuditedIR
from .lexicon import Lexicon
from .parser import parse
from .results import ClauseResult


class Translator:
    def __init__(self, profile, seed, fixed=None, uniform=False):
        self.profile = profile
        self.seed = seed
        self.features = profile.catalog.sample(seed, fixed=fixed, uniform=uniform)
        self.phonology = profile.phonology_class(self.features, seed, profile.language_id, profile.output_version)
        self.realizer = profile.realizer_class(self.features, self.phonology, seed, profile.language_id, profile.output_version)
        self.lexicon = Lexicon(seed, profile.language_id, profile.output_version, self.phonology)
        self.lexicon.register_function_forms(self.realizer.function_forms())

    def translate(self, text, check=False):
        if not text or not text.strip():
            return ClauseResult(text, [])
        try:
            ir = parse(text)
            audited = AuditedIR(ir)
            allowed = {field for feature in self.profile.catalog.features if feature.meaning_bearing and self.features[feature.id] is not None for field in feature.source_fields}
            words, rules = self.realizer.realize(audited.value, self.lexicon, lambda value: None)
            if check and not audited.passes(allowed):
                disallowed = sorted(path for path in audited.read_paths if not any(path == f or path.startswith(f + ".") or path.startswith(f + "[") for f in set(allowed) | set(__import__("conlang.core.ir", fromlist=["STRUCTURAL_FIELDS"]).STRUCTURAL_FIELDS)))
                rules.append("IR audit failed: " + ", ".join(disallowed))
            else:
                rules.append("IR audit passed.") if check else None
            for word in words:
                if word.literal:
                    word.surface()
                else:
                    word.surface(self.phonology.validate_surface, self.phonology.epenthetic_vowel)
            fallback_spans = [(0, len(text))] if ir.fragments else []
            return ClauseResult(text, words, rules, fallback_spans)
        except Exception as error:
            words = []
            try:
                from .parser import _model
                tokens = [token.text for token in _model()(text)]
            except Exception:
                tokens = text.split()
            from .words import Morpheme, Word
            for token in tokens:
                words.append(Word([Morpheme((token,), token, "root")], literal=True))
                words[-1].surface()
            return ClauseResult(text, words, [f"Unexpected {type(error).__name__}; word-by-word fallback used."], [(0, len(text))])