"""Austronesian profile realization from source-determined IR values."""

from collections.abc import Mapping
from types import MappingProxyType

from conlang.core.ir import UNSPECIFIED
from conlang.core.seeds import item_rng
from conlang.core.words import Morpheme, Word

TAM_TABLES: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        "tense3": MappingProxyType(
            {"past": "past", "present": "present", "future": "future", "UNSPECIFIED": "present"}
        ),
        "past_nonpast": MappingProxyType(
            {"past": "past", "present": "nonpast", "future": "nonpast", "UNSPECIFIED": "nonpast"}
        ),
    }
)

PERSONAL_PRONOUN_TABLE = MappingProxyType(
    {
        ("1", "singular"): ("P1SG", "P1"),
        ("1", "plural"): ("P1PL", "P1"),
        ("1", UNSPECIFIED): ("P1SG", "P1"),
        ("2", "singular"): ("P2", "P2"),
        ("2", "plural"): ("P2", "P2"),
        ("2", UNSPECIFIED): ("P2", "P2"),
        ("3", "singular"): ("P3SG", "P3"),
        ("3", "plural"): ("P3PL", "P3"),
        ("3", UNSPECIFIED): ("P3SG", "P3"),
        (UNSPECIFIED, "singular"): ("P2", "P2"),
        (UNSPECIFIED, "plural"): ("P2", "P2"),
        (UNSPECIFIED, UNSPECIFIED): ("P2", "P2"),
    }
)
VOICE_FOCUS_TABLE = MappingProxyType({"agent": "AF", "patient": "PF", "other": "AF"})


def personal_pronoun_form(person, number, number_strategy):
    sg_pl, unmarked = PERSONAL_PRONOUN_TABLE[(person, number)]
    return sg_pl if number_strategy == "sg_pl" else unmarked


def voice_focus(role):
    return VOICE_FOCUS_TABLE[role]


def article_label(system, definiteness):
    table: dict[str, dict[str, str | None]] = {
        "none": {"definite": None, "indefinite": None, "UNSPECIFIED": None, "none": None},
        "definite_only": {"definite": "DEF", "indefinite": None, "UNSPECIFIED": None, "none": None},
        "indefinite_only": {
            "definite": None,
            "indefinite": "INDEF",
            "UNSPECIFIED": None,
            "none": None,
        },
        "both": {"definite": "DEF", "indefinite": "INDEF", "UNSPECIFIED": None, "none": None},
    }
    return table[system][definiteness]


_ONES_WORDS = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
)


def _under_thousand(value):
    result = []
    if value >= 100:
        hundreds = value // 100
        if hundreds > 1:
            result.append(_ONES_WORDS[hundreds])
        result.append("hundred")
        value %= 100
    if value >= 20:
        tens = value // 10
        result.extend((_ONES_WORDS[tens], "ten"))
        value %= 10
    elif value >= 10:
        result.append("ten")
        value -= 10
    if value:
        result.append(_ONES_WORDS[value])
    return result


def numeral_words(value):
    if not isinstance(value, int) or not 0 <= value < 1_000_000_000:
        raise ValueError("numeral value must be an integer from 0 through 999,999,999")
    if value == 0:
        return ["zero"]
    result = []
    remainder = value
    for scale, label in ((1_000_000, "million"), (1_000, "thousand")):
        group, remainder = divmod(remainder, scale)
        if group:
            if group != 1:
                result.extend(_under_thousand(group))
            result.append(label)
    if remainder:
        result.extend(_under_thousand(remainder))
    return result


def tam_category(system, tense, perfect, progressive):
    if system in TAM_TABLES:
        return TAM_TABLES[system][tense]
    if tense == "future":
        return "contemplated"
    if (tense == "past" or perfect) and not progressive and tense != "future":
        return "perfective"
    return "imperfective"


class Realizer:
    MORPH_ORDER = (
        "DEF",
        "INDEF",
        "NOM",
        "ERG",
        "NEG",
        "P1SG",
        "P1PL",
        "P2",
        "P3SG",
        "P3PL",
        "P1",
        "P3",
        "PAST",
        "PRESENT",
        "FUTURE",
        "NONPAST",
        "PERF",
        "CONT",
        "IMPF",
        "AF",
        "PF",
        "PASS",
        "GEN",
        "OBL",
        "PL",
        "LINK",
        "PROX",
        "DIST",
        "QUESTION",
    )

    def __init__(self, features, phonology, seed, language_id, output_version, closed_class=()):
        self.features, self.phonology = features, phonology
        self.seed, self.language_id, self.output_version = seed, language_id, output_version
        self.closed_class = tuple(closed_class)
        self.forms = {}
        self.closed_forms = {}
        self._create_forms()

    def _active_morphs(self):
        names: list[str] = []
        alignment = self.features["alignment"]
        if self.features["case_particles"] == "preposed":
            if alignment == "symmetrical_voice":
                names.extend(("NOM", "GEN", "OBL"))
            elif alignment == "ergative":
                names.append("ERG")
            elif alignment == "active_passive":
                names.append("NOM")
        if alignment == "symmetrical_voice":
            names.extend(("AF", "PF"))
        elif alignment == "active_passive":
            names.extend(("AF", "PASS"))
        tam = {
            "tense3": ("PAST", "PRESENT", "FUTURE"),
            "past_nonpast": ("PAST", "NONPAST"),
            "aspect3": ("CONT", "PERF", "IMPF"),
        }[self.features["tam_system"]]
        names.extend(tam)
        if self.features["noun_number"] == "particle":
            names.append("PL")
        if self.features["linker"] == "particle":
            names.append("LINK")
        if self.features["demonstratives"] == "two_way":
            names.extend(("PROX", "DIST"))
        if self.features["question"] != "none":
            names.append("QUESTION")
        names.append("NEG")
        names.extend(
            ("P1SG", "P1PL", "P2", "P3SG", "P3PL")
            if self.features["pronoun_number"] == "sg_pl"
            else ("P1", "P2", "P3")
        )
        if self.features["articles"] in {"both", "definite_only"}:
            names.append("DEF")
        if self.features["articles"] in {"both", "indefinite_only"}:
            names.append("INDEF")
        needed = set(names)
        return [name for name in self.MORPH_ORDER if name in needed]

    def _new_form(self, rng, name):
        voice_affix = (
            name in {"AF", "PF", "PASS"} and self.features.get("voice_affix_position") is not None
        )
        tam_affix = (
            name in {"PAST", "PRESENT", "FUTURE", "NONPAST", "PERF", "CONT", "IMPF"}
            and self.features["tam_exponence"] == "affix"
        )
        affix_position = (
            self.features.get("voice_affix_position", "prefix")
            if voice_affix
            else self.features.get("tam_affix_position", "prefix")
        )
        if (voice_affix or tam_affix) and affix_position == "infix":
            return rng.choice(self.phonology.vowels) + rng.choice(self.phonology.codas)
        if voice_affix or tam_affix:
            vowel = rng.choice(self.phonology.vowels)
            consonant = rng.choices(
                self.phonology.consonants, self.phonology.consonant_weights, k=1
            )[0]
            return consonant + vowel
        count = 1 if name in {"DEF", "INDEF"} or rng.random() < 0.90 else 2
        return "".join(
            self.phonology.make_syllable(rng, allow_vowel_initial=index == 0, shape="function")
            for index in range(count)
        )

    def _short_form_groups(self, name, form_class):
        consonant_weights = dict(
            zip(self.phonology.consonants, self.phonology.consonant_weights, strict=True)
        )
        vowel_weights = dict(zip(self.phonology.vowels, self.phonology.vowel_weights, strict=True))
        coda_weights = dict(zip(self.phonology.codas, self.phonology.coda_weights, strict=True))
        voice_affix = (
            name in {"AF", "PF", "PASS"} and self.features.get("voice_affix_position") is not None
        )
        tam_affix = (
            name in {"PAST", "PRESENT", "FUTURE", "NONPAST", "PERF", "CONT", "IMPF"}
            and self.features["tam_exponence"] == "affix"
        )
        if form_class == "morph" and (voice_affix or tam_affix):
            position = (
                self.features.get("voice_affix_position", "prefix")
                if voice_affix
                else self.features.get("tam_affix_position", "prefix")
            )
            if position == "infix":
                return {
                    "VC": [
                        (vowel + coda, vowel_weights[vowel] * coda_weights[coda])
                        for vowel in self.phonology.vowels
                        for coda in self.phonology.codas
                    ]
                }
            return {
                "CV": [
                    (consonant + vowel, consonant_weights[consonant] * vowel_weights[vowel])
                    for consonant in self.phonology.consonants
                    for vowel in self.phonology.vowels
                ]
            }
        groups = {
            "CV": [
                (consonant + vowel, consonant_weights[consonant] * vowel_weights[vowel])
                for consonant in self.phonology.consonants
                for vowel in self.phonology.vowels
            ],
            "V": [(vowel, vowel_weights[vowel]) for vowel in self.phonology.vowels]
            if self.features["word_initial_vowel"] == "yes"
            else [],
            "CVC": [
                (
                    consonant + vowel + coda,
                    consonant_weights[consonant] * vowel_weights[vowel] * coda_weights[coda],
                )
                for consonant in self.phonology.consonants
                for vowel in self.phonology.vowels
                for coda in self.phonology.codas
            ]
            if self.features["syllable_structure"] != "open"
            else [],
        }
        return {key: values for key, values in groups.items() if values}

    def _unique_form(self, rng, name, used, make_form, form_class="particle"):
        short_groups = self._short_form_groups(name, form_class)
        shape_weights = {"CV": 0.60, "V": 0.30, "CVC": 0.10, "VC": 1.0}
        for _ in range(64):
            available_groups = {
                key: [
                    (candidate, weight) for candidate, weight in candidates if candidate not in used
                ]
                for key, candidates in short_groups.items()
            }
            available_groups = {
                key: candidates for key, candidates in available_groups.items() if candidates
            }
            if available_groups:
                shapes = list(available_groups)
                shape = rng.choices(shapes, [shape_weights[key] for key in shapes], k=1)[0]
                candidates, weights = zip(*available_groups[shape], strict=True)
                return rng.choices(candidates, weights=weights, k=1)[0]
            form = make_form(rng)
            if form not in used:
                return form
        fallback = item_rng(
            self.seed, self.language_id, self.output_version, "morph", f"{name}:fallback"
        )
        for _ in range(64):
            form = make_form(fallback) + self.phonology.make_syllable(fallback, shape="function")
            if form not in used:
                return form
        raise RuntimeError(f"could not generate unique function form for {name}")

    def _create_forms(self):
        used: set[str] = set()
        for name in self._active_morphs():
            rng = item_rng(self.seed, self.language_id, self.output_version, "morph", name)
            form = self._unique_form(
                rng,
                name,
                used,
                lambda source_rng, form_name=name: self._new_form(source_rng, form_name),
                "morph",
            )
            self.forms[name] = form
            used.add(form)
        for lemma, pos in self.closed_class:
            key = (lemma, pos)
            rng = item_rng(self.seed, self.language_id, self.output_version, "fn", f"{lemma}/{pos}")
            form = self._unique_form(
                rng,
                f"fn:{lemma}/{pos}",
                used,
                lambda source_rng, form_lemma=lemma, form_pos=pos: self.phonology.make_root(
                    source_rng, form_lemma, form_pos, shape="function"
                ),
                "function",
            )
            self.closed_forms[key] = form
            used.add(form)

    def function_forms(self):
        return set(self.forms.values()) | set(self.closed_forms.values())

    def function_morphs(self):
        forms = dict(self.forms)
        for (lemma, pos), form in self.closed_forms.items():
            key = lemma.upper()
            if key in forms:
                key = f"{key}/{pos}"
            forms[key] = form
        return forms

    def _m(self, name, kind=None):
        kind = kind or (
            "particle"
            if name in {"NOM", "GEN", "OBL", "ERG", "QUESTION", "NEG", "PL", "LINK", "PROX", "DIST"}
            else "prefix"
        )
        return Morpheme(tuple(self.phonology.segments(self.forms[name])), name, kind)

    def _root(self, lemma, pos, lexicon):
        form = lexicon.root(lemma, pos)
        return Word([Morpheme(tuple(self.phonology.segments(form)), lemma.upper(), "root")])

    @staticmethod
    def _dispose(token, disposition, reason=None):
        if token is not None and token.disposition is None:
            token.disposition = disposition
            token.disposition_reason = reason

    def _lexical_word(self, lemma, pos, lexicon, gloss=None):
        form = self.phonology.segments(lexicon.root(lemma, pos))
        return Word([Morpheme(tuple(form), gloss or lemma.upper(), "root")])

    def _literal_word(self, text):
        return Word([Morpheme((text,), text, "root")], literal=True)

    def _number_words(self, value, lexicon, rules, fallback_text=None):
        if value is None:
            raw_words = [
                part.lower()
                for part in (fallback_text or "").replace("-", " ").split()
                if part.lower() != "and"
            ]
            rules.append("unparsed numeral realized as individual NUM roots")
            names = raw_words
        else:
            names = numeral_words(value)
        return [self._root(name, "NUM", lexicon) for name in names]

    def numeral_sequence(self, value, lexicon):
        """Numeral words for a parsed value, as the noun-phrase path composes them."""
        return self._number_words(value, lexicon, [])

    def _pronoun_label(self, np):
        return personal_pronoun_form(np.person, np.number, self.features["pronoun_number"])

    def _np_words(self, np, lexicon, rules):
        kind = np.kind
        if kind == "proper" or np.literal:
            head_words = [self._literal_word(np.surface or np.head)]
        elif kind == "number":
            if np.numeral_value is not None:
                head_words = self._number_words(np.numeral_value, lexicon, rules, np.surface)
            elif np.literal:
                head_words = [self._literal_word(np.surface or np.head)]
            else:
                head_words = self._number_words(None, lexicon, rules, np.surface or np.head)
        elif kind == "pronoun":
            form_id = self._pronoun_label(np)
            head_words = [
                Word(
                    [Morpheme(tuple(self.phonology.segments(self.forms[form_id])), form_id, "root")]
                )
            ]
        elif kind == "demonstrative_pronoun" and self.features["demonstratives"] == "two_way":
            head_words = [self._function_word("PROX" if np.demonstrative == "proximal" else "DIST")]
        else:
            head_pos = np.pos or (
                "PRON"
                if kind in {"wh_pronoun", "other_pronoun", "demonstrative_pronoun"}
                else "NOUN"
            )
            head_words = [self._lexical_word(np.head, head_pos, lexicon)]

        if (
            self.features["noun_number"] != "none"
            and kind
            not in {
                "pronoun",
                "proper",
                "number",
                "wh_pronoun",
                "other_pronoun",
                "demonstrative_pronoun",
            }
            and np.number == "plural"
        ):
            number_strategy = self.features["noun_number"]
            if number_strategy == "particle":
                head_words.append(self._function_word("PL"))
            elif number_strategy in {"full_reduplication", "partial_reduplication"}:
                head_words[0].reduplicate(
                    number_strategy == "partial_reduplication", self.phonology.syllabify
                )

        modifier_groups = []
        for modifier in np.modifiers:
            modifier_kind = modifier.kind
            if modifier.literal or any(char.isdigit() for char in modifier.text):
                group = [self._literal_word(modifier.text)]
            elif modifier_kind == "numeral":
                group = self._number_words(modifier.value, lexicon, rules, modifier.text)
            else:
                group = [self._lexical_word(modifier.lemma.lower(), modifier.pos or "ADJ", lexicon)]
                sub_words = [
                    self._lexical_word(item.lemma.lower(), item.pos or "ADV", lexicon)
                    for item in modifier.sub_modifiers
                ]
                group = sub_words + group
            modifier_groups.append(group)
        modifier_words = [word for group in modifier_groups for word in group]

        demo_particle = []
        if (
            kind != "demonstrative_pronoun"
            and np.demonstrative != "none"
            and self.features["demonstratives"] == "two_way"
        ):
            demo_particle = [
                self._function_word("PROX" if np.demonstrative == "proximal" else "DIST")
            ]
        elif kind != "demonstrative_pronoun" and np.demonstrative != "none":
            demonstrative_token = next(
                (token for token in np.source_tokens if "Dem" in token.morph.get("PronType", ())),
                None,
            )
            if demonstrative_token is not None:
                demo_particle = [
                    self._lexical_word(
                        demonstrative_token.lemma.lower(), demonstrative_token.pos or "DET", lexicon
                    )
                ]
        if self.features["modifier_position"] == "before":
            core_words = modifier_words + head_words
        else:
            core_words = list(head_words)
            if modifier_words and self.features["linker"] == "particle":
                core_words.append(self._function_word("LINK"))
            core_words.extend(modifier_words)
        core_words = demo_particle + core_words

        article = None
        if self.features["articles"] != "none":
            article = article_label(self.features["articles"], np.definiteness)
        if article and self.features["article_position"] == "before":
            core_words.insert(0, self._function_word(article))
        elif article:
            core_words.append(self._function_word(article))

        if np.possessor is not None:
            possessor_words = self._np_words(np.possessor.np, lexicon, rules)
            if self.features["possessor_position"] == "before":
                core_words = possessor_words + core_words
            else:
                core_words.extend(possessor_words)

        for post_modifier in np.post_modifiers:
            if post_modifier.kind == "prep":
                if post_modifier.adposition:
                    core_words.append(self._lexical_word(post_modifier.adposition, "ADP", lexicon))
                if post_modifier.np is not None:
                    core_words.extend(self._np_words(post_modifier.np, lexicon, rules))
            elif post_modifier.kind == "clause" and post_modifier.link is not None:
                core_words.extend(self._realize_link(post_modifier.link, lexicon, rules))

        for coordination in np.coordinated:
            if coordination.conj is not None:
                conj = coordination.conj
                core_words.append(
                    self._lexical_word(conj.lemma.lower(), conj.pos or "CCONJ", lexicon)
                )
                self._dispose(conj, "realized")
            core_words.extend(self._np_words(coordination.np, lexicon, rules))

        for token in np.source_tokens:
            if token.disposition is None:
                if token.pos == "PUNCT":
                    self._dispose(token, "absorbed", "punctuation")
                elif token.dep == "det" and token.morph.get("Definite"):
                    label = self._determiner_label(token)
                    self._dispose(
                        token,
                        "realized" if label else "absorbed",
                        None if label else "article distinction merged",
                    )
                else:
                    self._dispose(token, "realized")
        return core_words

    def _determiner_label(self, token):
        if self.features["articles"] == "none":
            return None
        definiteness = "definite" if "Def" in token.morph.get("Definite", ()) else "indefinite"
        return article_label(self.features["articles"], definiteness)

    def determiner_word(self, token):
        """Realize a bare article token, or absorb it when the dialect has no matching article."""
        label = self._determiner_label(token)
        if label is None:
            self._dispose(token, "absorbed", "article distinction merged")
            return None
        self._dispose(token, "realized")
        return self._function_word(label)

    def _function_word(self, name):
        return Word([self._m(name, "particle")])

    def _realize_link(self, link, lexicon, rules):
        words = []
        if link.marker is not None:
            marker = link.marker
            words.append(self._lexical_word(marker.lemma.lower(), marker.pos or "SCONJ", lexicon))
            self._dispose(marker, "realized")
        words.extend(self._realize_clause(link.clause, lexicon, rules))
        return words

    def _realize_fragments(self, clause, lexicon, rules):
        sequence: list[Word] = []
        if clause.kind == "interjection":
            for token in clause.source_tokens:
                if token.pos == "INTJ":
                    lemma = (token.lemma or token.text).lower()
                    sequence.append(self._lexical_word(lemma, "INTJ", lexicon))
                    self._dispose(token, "realized")
            return sequence
        for argument in clause.arguments:
            sequence.extend(self._np_words(argument.np, lexicon, rules))
            for token in argument.source_tokens:
                self._dispose(token, "realized")
        return sequence

    def _realize_clause(self, clause, lexicon, rules):
        if clause.kind in {"nominal", "interjection"}:
            return self._realize_fragments(clause, lexicon, rules)
        verb = None
        if not (
            clause.predicate == "be" and clause.kind in {"equational", "locative", "existential"}
        ):
            verb = self._root(clause.predicate, clause.predicate_pos or "VERB", lexicon)
        if verb is not None and self.features["imperfective_reduplication"] == "yes":
            category = tam_category(
                self.features["tam_system"], clause.tense, clause.perfect, clause.progressive
            )
            if category == "imperfective":
                verb.reduplicate(True, self.phonology.syllabify)

        alignment = self.features["alignment"]
        if alignment == "symmetrical_voice" and verb is not None:
            pivot = next(
                (argument for argument in clause.arguments if argument.relation == "subject"), None
            )
            role = pivot.role if pivot is not None else "other"
            self._apply_affix(verb, voice_focus(role))
        elif alignment == "active_passive" and verb is not None:
            self._apply_affix(verb, "PASS" if clause.voice == "passive" else "AF")

        category = tam_category(
            self.features["tam_system"], clause.tense, clause.perfect, clause.progressive
        )
        tam_name = {
            "past": "PAST",
            "present": "PRESENT",
            "future": "FUTURE",
            "nonpast": "NONPAST",
            "contemplated": "CONT",
            "perfective": "PERF",
            "imperfective": "IMPF",
        }[category]
        tam_particle = None
        if self.features["tam_exponence"] == "particle":
            tam_particle = self._function_word(tam_name)
        else:
            self._apply_affix(verb, tam_name, self.features.get("tam_affix_position", "prefix"))

        initial: list[Word] = []
        final: list[Word] = []
        if clause.mood == "interrogative" and self.features["question"] != "none":
            (initial if self.features["question"] == "particle_initial" else final).append(
                self._function_word("QUESTION")
            )
        if clause.polarity == "negative" and self.features["negation"] == "clause_initial_particle":
            initial.append(self._function_word("NEG"))

        argument_words = []
        second_position_clitics = []
        for argument in clause.arguments:
            words = self._np_words(argument.np, lexicon, rules)
            is_core = argument.relation in {"subject", "object", "indirect_object"}
            is_personal = argument.np.kind == "pronoun"
            case_bearing_pivot = (
                self.features["case_particles"] == "preposed"
                and alignment in {"symmetrical_voice", "active_passive"}
                and argument.relation == "subject"
            )
            cliticized = (
                is_core
                and is_personal
                and not case_bearing_pivot
                and self.features["pronoun_strategy"] in {"clitic_verb", "clitic_second"}
            )
            if cliticized:
                pronoun_word = next(
                    (
                        word
                        for word in words
                        if word.morphemes and word.morphemes[0].gloss.startswith("P")
                    ),
                    None,
                )
                if pronoun_word is not None:
                    words.remove(pronoun_word)
                    if self.features["pronoun_strategy"] == "clitic_verb" and verb is not None:
                        for morpheme in pronoun_word.morphemes:
                            verb.cliticize(Morpheme(morpheme.segments, morpheme.gloss, "clitic"))
                    elif self.features["pronoun_strategy"] == "clitic_second":
                        second_position_clitics.append(pronoun_word)
                    else:
                        words.append(pronoun_word)

            if not cliticized and self.features["case_particles"] == "preposed":
                case = self._case(alignment, argument, clause)
                if case:
                    words.insert(0, self._function_word(case))
                elif argument.preposition and argument.relation in {"oblique", "indirect_object"}:
                    words.insert(0, self._lexical_word(argument.preposition, "ADP", lexicon))
            elif (
                not cliticized
                and argument.preposition
                and argument.relation in {"oblique", "indirect_object"}
            ):
                words.insert(0, self._lexical_word(argument.preposition, "ADP", lexicon))
            if argument.source_tokens:
                for token in argument.source_tokens:
                    self._dispose(token, "realized")
            argument_words.append((argument.relation, words))

        subjects = [
            word for relation, words in argument_words if relation == "subject" for word in words
        ]
        other_arguments = [
            word for relation, words in argument_words if relation != "subject" for word in words
        ]
        adverbs = [
            self._lexical_word(adverb.lemma.lower(), adverb.pos or "ADV", lexicon)
            for adverb in clause.adverbs
        ]
        predicate_token = next(
            (
                token
                for token in clause.source_tokens
                if token.lemma.lower() == clause.predicate and token.pos in {"VERB", "AUX"}
            ),
            None,
        )
        for token in clause.source_tokens:
            if (
                token.dep == "advmod"
                and predicate_token is not None
                and token.head_index == predicate_token.index
                and token.text.lower() not in {"not", "n't"}
            ):
                self._dispose(token, "realized")
        verb_slot = [verb] if verb is not None else []
        preverbal_negation = (
            [self._function_word("NEG")]
            if clause.polarity == "negative" and self.features["negation"] == "preverbal_particle"
            else []
        )
        verb_prefix = ([tam_particle] if tam_particle else []) + preverbal_negation
        order = self.features["clause_order"]
        if order == "VSO":
            sequence = initial + verb_prefix + verb_slot + subjects + other_arguments + adverbs
        elif order == "VOS":
            sequence = initial + verb_prefix + verb_slot + other_arguments + subjects + adverbs
        elif order == "SOV":
            sequence = initial + subjects + other_arguments + verb_prefix + verb_slot + adverbs
        else:
            sequence = initial + subjects + verb_prefix + verb_slot + other_arguments + adverbs
        sequence += final

        for clitic_word in second_position_clitics:
            if sequence:
                target = sequence[1] if len(sequence) > 1 else sequence[0]
                for morpheme in clitic_word.morphemes:
                    target.cliticize(Morpheme(morpheme.segments, morpheme.gloss, "clitic"))
            else:
                sequence.append(clitic_word)

        self._dispose(predicate_token, "realized")
        for token in clause.source_tokens:
            if token.pos == "AUX" or token.dep in {"aux", "auxpass"}:
                self._dispose(token, "absorbed", "auxiliary contributes tense, aspect, or voice")
            elif token.dep == "neg" or token.text.lower() in {"not", "n't"}:
                self._dispose(token, "absorbed", "polarity particle")
            elif token.pos == "PUNCT":
                self._dispose(token, "absorbed", "punctuation")

        for link in clause.links:
            sequence.extend(self._realize_link(link, lexicon, rules))
        return sequence

    def realize(self, ir, lexicon):
        rules = list(ir.rules)
        sequence = self._realize_clause(ir.clause, lexicon, rules)
        for token in ir.source_tokens:
            if token.disposition is not None:
                continue
            if (
                token.pos == "PUNCT"
                or token.text
                and not any(char.isalnum() for char in token.text)
            ):
                self._dispose(token, "absorbed", "punctuation")
            elif token.pos == "AUX" or token.dep in {"aux", "auxpass", "neg"}:
                self._dispose(token, "absorbed", "grammatical auxiliary or polarity marker")
            else:
                if any(char.isdigit() for char in token.text) or token.pos == "PROPN":
                    sequence.append(self._literal_word(token.text))
                else:
                    sequence.append(
                        self._lexical_word(
                            (token.lemma or token.text).lower(), token.pos or "X", lexicon
                        )
                    )
                self._dispose(token, "realized")
                rules.append(f"residual token: {token.text}")
        return sequence, rules

    def _apply_affix(self, word, name, position=None):
        if not word:
            return
        position = position or self.features.get("voice_affix_position", "prefix")
        morpheme = self._m(
            name, {"prefix": "prefix", "suffix": "suffix", "infix": "infix"}.get(position, "prefix")
        )
        if position == "suffix":
            word.add_suffix(morpheme)
        elif position == "infix":
            root = next((item for item in word.morphemes if item.kind == "root"), None)
            onset_length = (
                next(
                    (
                        index
                        for index, segment in enumerate(root.segments)
                        if segment in self.phonology.vowels
                    ),
                    1,
                )
                if root
                else 1
            )
            word.add_infix(morpheme, onset_length)
        else:
            word.add_prefix(morpheme)

    @staticmethod
    def _case(alignment, argument, clause):
        if alignment == "symmetrical_voice":
            if argument.relation == "subject":
                return "NOM"
            if argument.relation in {"object", "indirect_object"} or argument.role == "agent":
                return "GEN"
            return "OBL"
        if alignment == "ergative" and clause.transitivity and argument.role == "agent":
            return "ERG"
        if alignment == "active_passive" and argument.relation == "subject":
            return "NOM"
        return None
