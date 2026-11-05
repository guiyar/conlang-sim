"""Translator instance owning its dialect and lexical state."""

from .audit import AuditedIR
from .ir import TokenDispositionLedger
from .lexicon import Lexicon
from .parser import numeral_value, parse
from .results import ClauseResult


class Translator:
    def __init__(self, profile, seed, fixed=None, uniform=False):
        self.profile = profile
        self.seed = seed
        self.features = profile.catalog.sample(seed, fixed=fixed, uniform=uniform)
        self.phonology = profile.phonology_class(
            self.features, seed, profile.language_id, profile.output_version
        )
        self.realizer = profile.realizer_class(
            self.features,
            self.phonology,
            seed,
            profile.language_id,
            profile.output_version,
            closed_class=getattr(profile, "closed_class", ()),
        )
        self.lexicon = Lexicon(
            seed,
            profile.language_id,
            profile.output_version,
            self.phonology,
            shape_for_pos=getattr(profile, "word_shape", None),
            closed_forms=self.realizer.closed_forms,
            gloss_for=getattr(profile, "gloss_for", None),
            canonical_key=getattr(profile, "canonical_key", None),
        )
        self.lexicon.register_function_forms(self.realizer.function_forms())

    def function_morphs(self):
        return self.realizer.function_morphs()

    def translate(self, text, check=False):
        if not text or not text.strip():
            return []
        try:
            sentences = parse(text)
        except Exception as error:
            return [self._fallback_result(text, error)]
        results = []
        for sentence in sentences:
            try:
                if sentence.clause.kind == "rootless":
                    results.append(self._fallback_result(sentence.source_text, None, sentence))
                    continue
                dispositions = TokenDispositionLedger(sentence.source_tokens)
                audited = AuditedIR(sentence, dispositions)
                allowed = {
                    source_field
                    for feature in self.profile.catalog.features
                    if feature.meaning_bearing and self.features[feature.id] is not None
                    for source_field in feature.source_fields
                }
                try:
                    words, rules = self.realizer.realize(audited.value, self.lexicon)
                finally:
                    dispositions.sync(sentence.source_tokens)
                rules = list(rules)
                if check:
                    if audited.passes(allowed):
                        rules.append("IR audit passed.")
                    else:
                        rules.append("IR audit failed: undeclared IR field read.")
                self._surface_words(words)
                self._record_output(words)
                results.append(
                    ClauseResult(sentence.source_text, words, list(dict.fromkeys(rules)), [])
                )
            except Exception as error:
                results.append(self._fallback_result(sentence.source_text, error, sentence))
        return results

    def _surface_words(self, words):
        for word in words:
            if word.literal:
                word.realize()
            else:
                word.realize(self.phonology.validate_surface, self.phonology.epenthetic_vowel)

    def _record_output(self, words):
        for word in words:
            realized = word.realized
            if realized is None:
                raise RuntimeError("output word was not realized")
            for morpheme in realized.morphemes:
                form = "".join(morpheme.segments)
                if morpheme.gloss in self.realizer.forms:
                    self.lexicon.record(
                        form,
                        morpheme.gloss,
                        category="function",
                    )
                elif not word.literal and morpheme.kind == "root":
                    matching = next(
                        (
                            (lemma, pos, category)
                            for (lemma, pos), category, known in [
                                *((key, "lexical", f) for key, f in self.lexicon.entries.items()),
                                *(
                                    (key, "function", f)
                                    for key, f in self.lexicon.closed_forms.items()
                                ),
                            ]
                            if self.lexicon.gloss(lemma, pos) == morpheme.gloss and known == form
                        ),
                        None,
                    )
                    if matching is not None:
                        lemma, pos, category = matching
                        self.lexicon.record(form, morpheme.gloss, lemma, pos, category)
            if realized.literal:
                self.lexicon.literal(realized.surface(), realized.gloss())

    def _fallback_result(self, text, error=None, sentence=None):
        from .words import Morpheme, Word

        source_tokens = sentence.source_tokens if sentence is not None else []
        numeral_spans = list(sentence.numeral_spans) if sentence is not None else []
        if not source_tokens:
            try:
                from .parser import fallback_source

                source_tokens, numeral_spans = fallback_source(text)
            except Exception:
                source_tokens = []
        numerals = {}
        for start, end in numeral_spans:
            span = [
                token
                for token in source_tokens
                if token.index is not None and start <= token.index < end
            ]
            value = numeral_value(token.text for token in span)
            if value is not None:
                numerals[start] = (span, value)
        covered = {token.index for span, _ in numerals.values() for token in span}
        names = {}
        run: list = []
        for token in [*source_tokens, None]:
            if (
                token is not None
                and token.pos == "PROPN"
                and (not run or token.index == run[-1].index + 1)
            ):
                run.append(token)
                continue
            if len(run) > 1:
                names[run[0].index] = run
                covered.update(item.index for item in run[1:])
            run = [token] if token is not None and token.pos == "PROPN" else []
        words = []
        punctuation = []
        for token in source_tokens:
            sources = () if token.index is None else (token.index,)
            if token.index in numerals:
                span, value = numerals[token.index]
                words.extend(
                    self.realizer.numeral_sequence(
                        value, self.lexicon, tuple(item.index for item in span)
                    )
                )
                for item in span:
                    if item.pos == "CCONJ" and item.dep == "cc":
                        item.disposition, item.disposition_reason = (
                            "absorbed",
                            "numeral conjunction",
                        )
                    elif item.pos == "PUNCT":
                        item.disposition, item.disposition_reason = "absorbed", "punctuation"
                    elif item.dep == "det":
                        item.disposition, item.disposition_reason = (
                            "absorbed",
                            "numeral determiner",
                        )
                    else:
                        item.disposition = "realized"
                continue
            if token.index in names:
                name = names[token.index]
                words.append(
                    Word(
                        [
                            Morpheme(
                                (" ".join(item.text for item in name),),
                                " ".join(item.text for item in name),
                                "root",
                                sources=tuple(item.index for item in name),
                            )
                        ],
                        literal=True,
                    )
                )
                for item in name:
                    item.disposition = "realized"
                continue
            if token.index in covered:
                continue
            if (
                token.pos == "PUNCT"
                or token.text
                and not any(char.isalnum() for char in token.text)
            ):
                punctuation.append(token.text)
                token.disposition = "absorbed"
                token.disposition_reason = "punctuation"
                continue
            if token.dep == "det" and token.morph.get("Definite"):
                word = self.realizer.determiner_word(token)
                if word is not None:
                    words.append(word)
                continue
            if any(char.isdigit() for char in token.text) or token.pos == "PROPN":
                words.append(
                    Word(
                        [Morpheme((token.text,), token.text, "root", sources=sources)],
                        literal=True,
                    )
                )
                token.disposition = "realized"
                continue
            lemma = (token.lemma or token.text).lower()
            pos = token.pos or "X"
            form = self.lexicon.root(lemma, pos)
            words.append(
                Word(
                    [
                        Morpheme(
                            tuple(self.phonology.segments(form)),
                            self.lexicon.gloss(lemma, pos),
                            "root",
                            sources=sources,
                        )
                    ]
                )
            )
            token.disposition = "realized"
        if not source_tokens:
            for token in text.split():
                if any(char.isdigit() for char in token) or not any(
                    char.isalnum() for char in token
                ):
                    words.append(Word([Morpheme((token,), token, "root")], literal=True))
                else:
                    lemma = token.lower().strip(".,!?;:")
                    form = self.lexicon.root(lemma, "X")
                    words.append(
                        Word(
                            [Morpheme(tuple(self.phonology.segments(form)), lemma.upper(), "root")]
                        )
                    )
        self._surface_words(words)
        self._record_output(words)
        note = "No verbal root; token-by-token conlang fallback used."
        if error is not None:
            note = f"Unexpected {type(error).__name__}; token-by-token conlang fallback used."
        rules = list(sentence.rules) if sentence is not None else []
        return ClauseResult(text, words, list(dict.fromkeys([*rules, note])), [(0, len(text))])
