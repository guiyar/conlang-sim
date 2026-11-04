"""Seeded phoneme inventories and bounded syllable generation."""

from conlang.core.seeds import item_rng


class Phonology:
    def __init__(self, features, seed, language_id="austronesian", output_version=1):
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
        eligible_codas = list(dict.fromkeys(c for c in self.stops + self.nasals + self.liquids if len(c) == 1))
        coda_rng = item_rng(seed, language_id, output_version, "param", "coda_set")
        coda_rng.shuffle(eligible_codas)
        self.codas = eligible_codas[:max(3, min(len(eligible_codas), (len(eligible_codas) + 1) // 2))]
        self.structure = features["syllable_structure"]
        rng = item_rng(seed, language_id, output_version, "param", "phoneme_frequency")
        self.vowel_weights = [rng.randint(1, 5) for _ in self.vowels]
        self.consonant_weights = [rng.randint(1, 5) for _ in self.consonants]
        self.syllable_weights = [1, 3, 3, 1]
        self.epenthetic_vowel = item_rng(seed, language_id, output_version, "param", "epenthetic_vowel").choice(vowel_base)
        self.parameters = {"vowel_weights": self.vowel_weights, "consonant_weights": self.consonant_weights,
                           "syllable_weights": self.syllable_weights, "coda_set": self.codas,
                           "epenthetic_vowel": self.epenthetic_vowel}

    def make_syllable(self, rng, allow_vowel_initial=False):
        vowel = rng.choices(self.vowels, self.vowel_weights, k=1)[0]
        onset = rng.choices(self.consonants, self.consonant_weights, k=1)[0]
        if allow_vowel_initial and self.features["word_initial_vowel"] == "yes" and rng.random() < 0.12:
            return vowel
        if self.structure == "open":
            return onset + vowel
        if self.structure == "closed":
            return onset + vowel + rng.choice(self.codas)
        liquid = rng.choice(self.liquids)
        onset = rng.choice(self.stops + self.fricatives) + liquid
        return onset + vowel + rng.choice(self.codas)

    def make_root(self, rng, lemma="", pos=""):
        count = rng.choices([1, 2, 3, 4], self.syllable_weights, k=1)[0]
        if self.structure != "open":
            count = max(2, count)
        candidate = ""
        for _ in range(64):
            candidate = "".join(self.make_syllable(rng, allow_vowel_initial=False) for _ in range(count))
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
                    if segments[index] in self.stops + self.fricatives and segments[index + 1] in self.liquids:
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
        def score(candidate):
            parsed = self.segments("".join(candidate))
            return (0 if self.valid(parsed) else 1, 0 if parsed == candidate else 1)

        current_score = score(result)
        if current_score != (0, 0):
            seen = {tuple(result)}
            for _ in range(min(64, len(result) + 1)):
                best = None
                best_score = current_score
                for position in range(len(result) + 1):
                    candidate = result[:position] + [epenthetic_vowel] + result[position:]
                    signature = tuple(candidate)
                    if signature in seen:
                        continue
                    candidate_score = score(candidate)
                    if candidate_score == (0, 0):
                        result = candidate
                        best = candidate
                        best_score = candidate_score
                        break
                    if candidate_score < best_score:
                        best, best_score = candidate, candidate_score
                if best is None:
                    break
                result = list(best)
                seen.add(tuple(result))
                current_score = best_score
                if current_score == (0, 0):
                    break
            if current_score != (0, 0):
                # Last-resort repair keeps the lexical material in order and separates consonant runs.
                repaired = []
                for segment in result:
                    if repaired and repaired[-1] in self.consonants and segment in self.consonants:
                        repaired.append(epenthetic_vowel)
                    repaired.append(segment)
                if repaired and repaired[-1] in self.consonants and repaired[-1] not in self.codas:
                    repaired.append(epenthetic_vowel)
                result = repaired
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