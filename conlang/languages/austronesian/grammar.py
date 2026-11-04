"""Austronesian profile realization from source-determined IR values."""

from conlang.core.seeds import item_rng
from conlang.core.words import Morpheme, Word

TAM_TABLES = {
    "tense3": {"past": "past", "present": "present", "future": "future", "UNSPECIFIED": "present"},
    "past_nonpast": {"past": "past", "present": "nonpast", "future": "nonpast", "UNSPECIFIED": "nonpast"},
}


def tam_category(system, tense, perfect, progressive):
    if system in TAM_TABLES:
        return TAM_TABLES[system][tense]
    if tense == "future":
        return "contemplated"
    if (tense == "past" or perfect) and not progressive and tense != "future":
        return "perfective"
    return "imperfective"


class Realizer:
    def __init__(self, features, phonology, seed, language_id, output_version):
        self.features, self.phonology = features, phonology
        self.seed, self.language_id, self.output_version = seed, language_id, output_version
        self.forms = {}
        self._create_forms()

    def _create_forms(self):
        names = ["NOM", "GEN", "OBL", "ERG", "AF", "PF", "PASS", "PAST", "PRESENT", "FUTURE",
                 "NONPAST", "PERF", "PROG", "CONT", "IMPF", "PL", "LINK", "PROX", "DIST",
                 "QUESTION", "NEG", "OBJ", "SUBJ", "IOBJ", "CLITIC", "P1SG", "P1PL", "P2", "P3SG", "P3PL", "P1", "P3"]
        for name in names:
            rng = item_rng(self.seed, self.language_id, self.output_version, "morph", name)
            voice_affix = name in {"AF", "PF", "PASS"} and self.features.get("voice_affix_position") is not None
            tam_affix = name in {"PAST", "PRESENT", "FUTURE", "NONPAST", "PERF", "PROG", "CONT", "IMPF"} and self.features["tam_exponence"] == "affix"
            pronoun_form = name in {"P1SG", "P1PL", "P2", "P3SG", "P3PL", "P1", "P3"}
            if voice_affix and self.features["voice_affix_position"] == "infix":
                form = rng.choice(self.phonology.vowels) + rng.choice(self.phonology.codas)
            elif voice_affix or tam_affix or pronoun_form:
                form = rng.choice(self.phonology.consonants) + rng.choice(self.phonology.vowels)
            else:
                count = rng.choice([1, 1, 2])
                form = "".join(self.phonology.make_syllable(rng) for _ in range(count))
            self.forms[name] = form

    def function_forms(self):
        return set(self.forms.values())

    def _m(self, name, kind=None):
        kind = kind or ("particle" if name in {"NOM", "GEN", "OBL", "ERG", "QUESTION", "NEG", "PL", "LINK", "PROX", "DIST"} else "prefix")
        return Morpheme(tuple(self.phonology.segments(self.forms[name])), name, kind)

    def _root(self, lemma, pos, lexicon):
        form = lexicon.root(lemma, pos)
        return Word([Morpheme(tuple(self.phonology.segments(form)), lemma.upper(), "root")])

    def _np_words(self, np, relation, role, lexicon, audit):
        kind = np.kind
        if kind == "proper":
            head = Word([Morpheme((np.surface or np.head,), np.surface or np.head, "root")], literal=True)
        elif kind == "number":
            head = Word([Morpheme((np.surface or np.head,), np.surface or np.head, "root")], literal=True)
        elif kind == "pronoun":
            person, number = np.person, np.number
            audit(np.person); audit(np.number)
            if self.features["pronoun_number"] == "sg_pl":
                form_id = {("1", "singular"): "P1SG", ("1", "plural"): "P1PL", ("2", "singular"): "P2", ("2", "plural"): "P2", ("2", "UNSPECIFIED"): "P2", ("3", "singular"): "P3SG", ("3", "plural"): "P3PL"}.get((person, number), "P3SG")
            else:
                form_id = {"1": "P1", "2": "P2", "3": "P3"}.get(person, "P3")
            head = Word([Morpheme(tuple(self.phonology.segments(self.forms[form_id])), form_id, "root")])
        elif kind == "demonstrative_pronoun" and self.features["demonstratives"] == "two_way":
            audit(np.demonstrative)
            head = self._root(np.head, "NOUN", lexicon)
            head.add_prefix(self._m("PROX" if np.demonstrative == "proximal" else "DIST", "particle"))
        else:
            head = self._root(np.head, "NOUN", lexicon)

        if kind == "demonstrative_pronoun":
            audit(np.demonstrative)
        if kind not in {"pronoun", "proper", "number"}:
            audit(np.number)
            if np.number == "plural":
                number = self.features["noun_number"]
                if number == "particle":
                    head.add_suffix(self._m("PL"))
                elif number in {"full_reduplication", "partial_reduplication"}:
                    head.reduplicate(number == "partial_reduplication", self.phonology.syllabify)
        modifier_words = []
        audit(np.modifiers)
        modifier_values = list(np.modifiers)
        if self.features["demonstratives"] == "two_way" and np.demonstrative != "none":
            modifier_values = [value for value in modifier_values if getattr(value, "lemma", value).lower() not in {"this", "that", "these", "those"}]
        for modifier in modifier_values:
            modifier_kind = getattr(modifier, "kind", "modifier")
            modifier_text = getattr(modifier, "text", modifier)
            modifier_lemma = getattr(modifier, "lemma", modifier_text).lower()
            if modifier_kind in {"numeral", "proper"}:
                modifier_words.append(Word([Morpheme((modifier_text,), modifier_text, "root")], literal=True))
            else:
                modifier_words.append(self._root(modifier_lemma, "ADJ", lexicon))
        if self.features["modifier_position"] == "before":
            words = modifier_words + [head]
        else:
            words = [head] + modifier_words
            if modifier_words and self.features.get("linker") == "particle":
                words.insert(1, self._function_word("LINK"))
        if kind != "demonstrative_pronoun" and np.demonstrative != "none":
            audit(np.demonstrative)
            if self.features["demonstratives"] == "two_way":
                words.insert(0, self._function_word("PROX" if np.demonstrative == "proximal" else "DIST"))
        audit(np.possessor)
        if np.possessor:
            possessor = self._root(str(np.possessor).lower(), "NOUN", lexicon)
            words = ([possessor] + words) if self.features["possessor_position"] == "before" else (words + [possessor])
        return words

    def _function_word(self, name):
        return Word([self._m(name, "particle")])

    def realize(self, ir, lexicon, audit=lambda value: None):
        clause = ir.clause
        audit(clause.predicate)
        audit(clause.arguments)
        if clause.fragments:
            words = [Word([Morpheme((token,), token, "root")], literal=True) for fragment in clause.fragments for token in fragment]
            return words, list(ir.rules) + ["Fragment fallback: source tokens emitted word-by-word."]

        verb = self._root(clause.predicate, clause.predicate_pos or "VERB", lexicon)
        if clause.kind in {"equational", "locative", "existential"} and clause.predicate == "be":
            verb = None
        audit(clause.voice); audit(clause.transitivity)
        alignment = self.features["alignment"]
        if alignment == "symmetrical_voice":
            subject_role = next((arg.role for arg in clause.arguments if arg.relation == "subject"), "other")
            affix = "AF" if subject_role == "agent" else "PF"
            self._apply_affix(verb, affix)
        elif alignment == "active_passive":
            self._apply_affix(verb, "PASS" if clause.voice == "passive" else "AF")
        audit(clause.tense); audit(clause.perfect); audit(clause.progressive)
        tam = tam_category(self.features["tam_system"], clause.tense, clause.perfect, clause.progressive)
        if self.features["tam_exponence"] == "particle":
            tam_word = self._function_word({"past": "PAST", "present": "PRESENT", "future": "FUTURE", "nonpast": "NONPAST", "contemplated": "CONT", "perfective": "PERF", "imperfective": "IMPF"}[tam])
        else:
            name = {"past": "PAST", "present": "PRESENT", "future": "FUTURE", "nonpast": "NONPAST", "contemplated": "CONT", "perfective": "PERF", "imperfective": "IMPF"}[tam]
            self._apply_affix(verb, name, self.features.get("tam_affix_position", "prefix"))
            tam_word = None
        if self.features.get("imperfective_reduplication") == "yes" and tam == "imperfective" and verb:
            verb.reduplicate(True, self.phonology.syllabify)
        audit(clause.mood); audit(clause.polarity)
        initial = []
        final = []
        if clause.mood == "interrogative" and self.features["question"] != "none":
            target = initial if self.features["question"] == "particle_initial" else final
            target.append(self._function_word("QUESTION"))
        if clause.polarity == "negative":
            if self.features["negation"] == "clause_initial_particle":
                initial.append(self._function_word("NEG"))
        argument_words = []
        second_position_clitics = []
        for argument in clause.arguments:
            audit(argument.relation); audit(argument.role)
            np_words = self._np_words(argument.np, argument.relation, argument.role, lexicon, audit)
            pronoun_word = np_words[0] if argument.np.kind == "pronoun" and np_words else None
            if self.features["case_particles"] == "preposed":
                case = self._case(alignment, argument, clause)
                if case:
                    np_words.insert(0, self._function_word(case))
            elif argument.relation in {"oblique", "indirect_object"} and argument.preposition:
                np_words.insert(0, self._root(argument.preposition, "ADP", lexicon))
            if pronoun_word and self.features["pronoun_strategy"] == "clitic_verb" and verb:
                np_words.remove(pronoun_word)
                for morpheme in pronoun_word.morphemes:
                    verb.cliticize(Morpheme(morpheme.segments, morpheme.gloss, "clitic"))
            elif pronoun_word and self.features["pronoun_strategy"] == "clitic_second":
                second_position_clitics.append(pronoun_word)
                np_words.remove(pronoun_word)
            argument_words.append((argument.relation, np_words))
        verb_slot = [verb] if verb else []
        before_verb = initial + ([tam_word] if tam_word else [])
        preverbal = [self._function_word("NEG")] if self.features["negation"] == "preverbal_particle" and clause.polarity == "negative" else []
        order = self.features["clause_order"]
        subjects = [w for rel, words in argument_words if rel == "subject" for w in words]
        objects = [w for rel, words in argument_words if rel in {"object", "indirect_object", "oblique"} for w in words]
        audit(clause.adverbs)
        objects.extend(self._root(adverb, "ADV", lexicon) for adverb in clause.adverbs)
        if order == "VSO":
            sequence = before_verb + preverbal + verb_slot + subjects + objects
        elif order == "VOS":
            sequence = before_verb + preverbal + verb_slot + objects + subjects
        elif order == "SOV":
            sequence = before_verb + subjects + objects + preverbal + verb_slot
        else:
            sequence = before_verb + subjects + preverbal + verb_slot + objects
        sequence += final
        for clitic_word in second_position_clitics:
            if sequence:
                target = sequence[min(1, len(sequence) - 1)]
                for morpheme in clitic_word.morphemes:
                    target.cliticize(Morpheme(morpheme.segments, morpheme.gloss, "clitic"))
            else:
                sequence.append(clitic_word)
        if not sequence and clause.source_tokens:
            sequence = [Word([Morpheme(tuple(t.text), t.text, "root")]) for t in clause.source_tokens]
        rules = list(ir.rules)
        for word in sequence:
            if word:
                word._validator = self.phonology.validate_surface
        return sequence, rules

    def _apply_affix(self, word, name, position=None):
        if not word:
            return
        position = position or self.features.get("voice_affix_position", "prefix")
        morpheme = self._m(name, {"prefix": "prefix", "suffix": "suffix", "infix": "infix"}.get(position, "prefix"))
        if position == "suffix":
            word.add_suffix(morpheme)
        elif position == "infix":
            root = next((item for item in word.morphemes if item.kind == "root"), None)
            onset_length = next((index for index, segment in enumerate(root.segments) if segment in self.phonology.vowels), 1) if root else 1
            word.add_infix(morpheme, onset_length)
        else:
            word.add_prefix(morpheme)

    @staticmethod
    def _case(alignment, argument, clause):
        if alignment == "symmetrical_voice":
            pivot_role = next((a.role for a in clause.arguments if a.relation == "subject"), "other")
            if argument.role == pivot_role:
                return "NOM"
            return "OBL" if argument.relation == "oblique" else "GEN"
        if alignment == "ergative" and clause.transitivity and argument.role == "agent":
            return "ERG"
        if alignment == "active_passive" and argument.relation == "subject":
            return "NOM"
        return None