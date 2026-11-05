"""Seeded phoneme inventories and bounded syllable generation."""

from conlang.core.seeds import item_rng
from .catalog import OUTPUT_VERSION


class Phonology:
    def __init__(self, features, seed, language_id="austronesian", output_version=OUTPUT_VERSION):
        self.features = features
        self.seed = seed
        self.language_id = language_id
        self.output_version = output_version
        self.parameters = {}
        vowel_base = ["a", "i", "u"] if features["vowels"] == "v3" else ["a", "e", "i", "o", "u"]
        self.vowels = list(vowel_base)
        if features["vowel_length"] == "contrastive":
            self.vowels += [v + v for v in vowel_base]
        self.stops = ["p", "t", "k"] + (["b", "d", "g"] if features["stop_voicing"] == "voiced_and_voiceless" else [])
        self.prenasals = ["mb", "nd", "ngg"] if features["prenasalized_stops"] == "yes" else []
        self.glottals = ["'"] if features["glottal_stop"] == "yes" else []
        self.fricatives = {"h": ["h"], "h_s": ["h", "s"], "h_s_f_v": ["h", "s", "f", "v"]}[features["fricatives"]]
        self.nasals = {"m_n": ["m", "n"], "m_n_ng": ["m", "n", "ng"], "m_n_ng_ny": ["m", "n", "ng", "ny"]}[features["nasals"]]
        self.liquids = {"l": ["l"], "r": ["r"], "l_r": ["l", "r"]}[features["liquids"]]
        self.glides = ["w", "y"]
        self.consonants = list(dict.fromkeys(self.stops + self.prenasals + self.glottals + self.fricatives + self.nasals + self.liquids + self.glides))
        eligible_codas = [c for c in ("ng", "m", "n", "k", "p", "t", "l", "r", "'") if c in self.consonants]
        coda_rng = item_rng(seed, language_id, output_version, "param", "coda_set")
        coda_weights = {"ng": 5.0, "m": 5.0, "n": 6.0, "k": 5.0, "p": 2.0, "t": 3.0, "l": 2.0, "r": 2.0, "'": 0.5}
        count = max(3, min(len(eligible_codas), (len(eligible_codas) + 1) // 2))
        selected = []
        if "ng" in eligible_codas:
            selected.append("ng")
            eligible_codas.remove("ng")
        while len(selected) < count and eligible_codas:
            chosen = coda_rng.choices(eligible_codas, [coda_weights[item] for item in eligible_codas], k=1)[0]
            selected.append(chosen)
            eligible_codas.remove(chosen)
        self.codas = selected
        self.structure = features["syllable_structure"]
        vowel_base_weights = {"a": 10.0, "i": 5.0, "u": 4.5, "e": 2.0, "o": 2.0}
        consonant_base_weights = {
            "n": 6.0, "k": 6.0, "t": 6.0, "m": 6.0, "l": 6.0, "h": 6.0,
            "s": 6.0, "p": 6.0, "ng": 2.5, "w": 3.0, "y": 3.0,
            "r": 4.0, "i": 1.0, "b": 1.2, "d": 1.2, "g": 1.2,
            "mb": 0.6, "nd": 0.6, "ngg": 0.6, "f": 1.2, "v": 1.0,
            "ny": 0.8, "'": 0.8,
        }
        self.phoneme_jitter = {}
        def weighted_inventory(inventory, bases, long_factor=1.0):
            result = []
            for segment in inventory:
                base_segment = segment[:1] if len(segment) == 2 and segment[0] == segment[1] else segment
                base = bases.get(base_segment, 1.0) * (long_factor if base_segment != segment else 1.0)
                jitter = item_rng(seed, language_id, output_version, "param", f"phoneme_jitter:{segment}").uniform(0.5, 1.5)
                self.phoneme_jitter[segment] = jitter
                result.append(base * jitter)
            return result
        self.vowel_weights = weighted_inventory(self.vowels, vowel_base_weights, 0.15)
        self.consonant_weights = weighted_inventory(self.consonants, consonant_base_weights)
        self.coda_weights = [coda_weights.get(coda, 1.0) for coda in self.codas]
        self.coda_probability = item_rng(seed, language_id, output_version, "param", "coda_prob").uniform(0.30, 0.35)
        self.cluster_probability = item_rng(seed, language_id, output_version, "param", "cluster_prob").uniform(0.08, 0.16)
        self.syllable_weights = [0.05, 0.60, 0.28, 0.07]
        self.function_syllable_weights = [0.85, 0.15]
        self.numeral_syllable_weights = [0.55, 0.45]
        self.epenthetic_vowel = item_rng(seed, language_id, output_version, "param", "epenthetic_vowel").choice(vowel_base)
        self.parameters = {"vowel_weights": self.vowel_weights, "consonant_weights": self.consonant_weights,
                           "syllable_weights": self.syllable_weights, "coda_set": self.codas,
                           "coda_probability": self.coda_probability, "cluster_probability": self.cluster_probability,
                           "phoneme_jitter": self.phoneme_jitter, "epenthetic_vowel": self.epenthetic_vowel}

    def make_syllable(self, rng, allow_vowel_initial=False, shape="content"):
        vowel = rng.choices(self.vowels, self.vowel_weights, k=1)[0]
        allow_vowel = allow_vowel_initial and self.features["word_initial_vowel"] == "yes"
        if shape == "function":
            templates = [("CV", 0.60), ("V", 0.30 if allow_vowel else 0.0), ("CVC", 0.10 if self.codas else 0.0)]
            template = rng.choices([item[0] for item in templates], [item[1] for item in templates], k=1)[0]
            if template == "V":
                return vowel
            onset = self._weighted_choice(rng, self.consonants, self.consonant_weights)
            if template == "CVC":
                return onset + vowel + self._weighted_choice(rng, self.codas, self.coda_weights)
            return onset + vowel

        onset_options = self.consonants
        onset_weights = self.consonant_weights
        if self.structure == "closed_clusters" and rng.random() < self.cluster_probability:
            combinations = [(stop, liquid) for stop in self.stops for liquid in self.liquids
                            if (stop, liquid) not in {("t", "l"), ("d", "l")}]
            if combinations:
                first_weights = [self._weight(stop) * self._weight(liquid) for stop, liquid in combinations]
                first, second = self._weighted_choice(rng, combinations, first_weights)
                onset = first + second
            else:
                onset = self._weighted_choice(rng, onset_options, onset_weights)
        else:
            onset = self._weighted_choice(rng, onset_options, onset_weights)
        if allow_vowel and rng.random() < 0.40:
            onset = ""
        coda = ""
        if self.structure != "open" and self.codas and rng.random() < self.coda_probability:
            coda = self._weighted_choice(rng, self.codas, self.coda_weights)
        return onset + vowel + coda

    @staticmethod
    def _weighted_choice(rng, items, weights):
        return rng.choices(items, weights=weights, k=1)[0]

    def _weight(self, segment):
        try:
            return self.consonant_weights[self.consonants.index(segment)]
        except ValueError:
            return 1.0

    def make_root(self, rng, lemma="", pos="", shape="content"):
        if shape == "function":
            count = rng.choices([1, 2], self.function_syllable_weights, k=1)[0]
        elif shape == "numeral":
            count = rng.choices([1, 2], self.numeral_syllable_weights, k=1)[0]
        else:
            count = rng.choices([1, 2, 3, 4], self.syllable_weights, k=1)[0]
        if shape != "content":
            initial_vowel_safe = True
        elif pos == "NOUN":
            initial_vowel_safe = self.features["noun_number"] not in {"full_reduplication", "partial_reduplication"}
        elif pos in {"ADJ", "ADV"}:
            initial_vowel_safe = True
        elif pos == "VERB":
            affix_positions = []
            if self.features["alignment"] in {"symmetrical_voice", "active_passive"}:
                affix_positions.append(self.features.get("voice_affix_position"))
            if self.features["tam_exponence"] == "affix":
                affix_positions.append(self.features.get("tam_affix_position"))
            initial_vowel_safe = (
                self.features["imperfective_reduplication"] != "yes"
                and all(position not in {"prefix", "infix"} for position in affix_positions)
            )
        else:
            initial_vowel_safe = False
        candidate = ""
        for _ in range(64):
            candidate = "".join(self.make_syllable(
                rng,
                allow_vowel_initial=(
                    index == 0
                    and self.features["word_initial_vowel"] == "yes"
                    and initial_vowel_safe
                ),
                shape=shape,
            )
                                 for index in range(count))
            if self.valid(self.segments(candidate)):
                return candidate
        onset = next((segment for segment in self.stops if segment in self.consonants), self.consonants[0])
        vowel = next((segment for segment in self.vowels if len(segment) == 1), self.vowels[0])
        return (onset + vowel) * count

    def valid(self, segments):
        from functools import lru_cache
        if not segments or any(segment not in self.vowels + self.consonants for segment in segments):
            return False
        @lru_cache(maxsize=None)
        def parse(index):
            if index == len(segments):
                return True
            if index == 0 and self.features["word_initial_vowel"] == "yes" and segments[index] in self.vowels:
                if parse(index + 1):
                    return True
            starts = []
            if segments[index] in self.consonants:
                starts.append((index + 1, False))
                if self.structure == "closed_clusters" and index + 1 < len(segments):
                    if segments[index] in self.stops and segments[index + 1] in self.liquids and (segments[index], segments[index + 1]) not in {("t", "l"), ("d", "l")}:
                        starts.append((index + 2, False))
            for vowel_index, _ in starts:
                if vowel_index >= len(segments) or segments[vowel_index] not in self.vowels:
                    continue
                next_index = vowel_index + 1
                if self.structure != "open" and next_index < len(segments) and segments[next_index] in self.codas:
                    if parse(next_index + 1):
                        return True
                if parse(next_index):
                    return True
            return False
        return parse(0)

    def validate_surface(self, segments, notes, epenthetic_vowel):
        result = list(segments)
        if self.segments("".join(result)) == result and self.valid(result):
            return result
        repaired = []
        for segment in result:
            if repaired and repaired[-1] in self.consonants and segment in self.consonants:
                repaired.append(epenthetic_vowel)
            repaired.append(segment)
        if repaired and repaired[-1] in self.consonants:
            if self.structure == "open" or repaired[-1] not in self.codas:
                repaired.append(epenthetic_vowel)
        result = repaired
        if not self.valid(result):
            repaired = []
            for segment in result:
                if repaired and repaired[-1] in self.consonants and segment in self.consonants:
                    repaired.append(epenthetic_vowel)
                repaired.append(segment)
                if segment in self.consonants and (not repaired or repaired[-1] != epenthetic_vowel):
                    repaired.append(epenthetic_vowel)
            result = repaired
        if result != list(segments):
            notes.append("epenthetic vowel inserted to satisfy spelling and syllable structure")
        return result

    def segments(self, text):
        inventory = sorted(set(self.vowels + self.consonants), key=lambda item: (-len(item), item))
        result = []
        index = 0
        while index < len(text):
            match = next((segment for segment in inventory if text.startswith(segment, index)), None)
            if match is None:
                result.append(text[index])
                index += 1
            else:
                result.append(match)
                index += len(match)
        return result

    def syllabify(self, segments):
        syllables = []
        current = []
        for segment in segments:
            current.append(segment)
            if segment in self.vowels:
                syllables.append(tuple(current))
                current = []
        if current:
            if syllables:
                syllables[-1] += tuple(current)
            else:
                syllables.append(tuple(current))
        return syllables