"""Interpret spaCy morphology and dependencies as grammatical categories."""

from ..ir import UNSPECIFIED


class GrammarAnalyzer:
    NOT_MODAL = frozenset({"will", "would"})

    @staticmethod
    def morph_value(token, key, allowed):
        values = token.morph.get(key)
        return values[0].lower() if values and values[0].lower() in allowed else UNSPECIFIED

    @staticmethod
    def degree(token):
        degree = token.morph.get("Degree")
        return {"Cmp": "comparative", "Sup": "superlative"}.get(degree[0] if degree else "", "none")

    @staticmethod
    def is_clause_head(token):
        if token.dep_ in {"aux", "auxpass"}:
            return False
        return (
            token.pos_ == "VERB"
            or token.lemma_.lower() == "be"
            and token.pos_
            in {
                "AUX",
                "VERB",
            }
        )

    @staticmethod
    def belongs_to(token, root):
        """True when `root` is the nearest clause head above `token`."""
        while token.head.i != token.i:
            token = token.head
            if token.i == root.i:
                return True
            if GrammarAnalyzer.is_clause_head(token):
                return False
        return False

    @staticmethod
    def analyze_clause(root, sentence, main):
        children = list(root.children)
        voice = "passive" if any(child.dep_ == "nsubjpass" for child in children) else "active"
        auxiliaries = [child for child in children if child.dep_ in {"aux", "auxpass"}]
        finite = next(
            (child for child in auxiliaries if child.morph.get("VerbForm") == ["Fin"]), root
        )
        has_will = any(
            child.lemma_.lower() == "will" or child.text.lower() == "wo" for child in auxiliaries
        )
        tense = "future" if has_will else UNSPECIFIED
        if not has_will and finite.tag_ != "MD" and finite.morph.get("VerbForm") == ["Fin"]:
            raw = GrammarAnalyzer.morph_value(finite, "Tense", {"past", "pres"})
            tense = {"past": "past", "pres": "present"}.get(raw, UNSPECIFIED)
        has_have = any(child.lemma_.lower() == "have" for child in auxiliaries)
        perfect_be = any(
            child.lemma_.lower() == "be" and child.tag_ == "VBN" for child in auxiliaries
        )
        perfect = has_have and (root.tag_ == "VBN" or root.tag_ == "VBG" and perfect_be)
        progressive = root.tag_ == "VBG" and any(
            child.lemma_.lower() == "be" for child in auxiliaries
        )
        subject = next((child for child in children if child.dep_ in {"nsubj", "nsubjpass"}), None)
        inversion = bool(
            subject and (root.i < subject.i or any(aux.i < subject.i for aux in auxiliaries))
        )
        interrogative = main and (
            sentence.text.rstrip().endswith("?")
            or inversion
            or any(
                token.tag_ in {"WP", "WRB", "WDT"} and GrammarAnalyzer.belongs_to(token, root)
                for token in sentence
            )
        )
        imperative = (
            main
            and root.tag_ == "VB"
            and subject is None
            and all(aux.lemma_.lower() == "do" for aux in auxiliaries)
            and not interrogative
        )
        mood = "interrogative" if interrogative else "imperative" if imperative else "declarative"
        expletive = any(child.dep_ == "expl" for child in children)
        if root.lemma_.lower() == "be":
            kind = (
                "existential"
                if expletive
                else (
                    "equational"
                    if any(child.dep_ in {"attr", "acomp"} for child in children)
                    else "locative"
                    if any(child.dep_ == "prep" for child in children)
                    else "equational"
                )
            )
        else:
            kind = "existential" if expletive else "verbal"
        return children, voice, tense, perfect, progressive, mood, kind
