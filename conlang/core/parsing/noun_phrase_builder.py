"""Build noun phrases and their modifiers from spaCy dependency analysis."""

from typing import Any

from ..ir import (
    UNSPECIFIED,
    ClauseLink,
    Coordination,
    Definiteness,
    Demonstrative,
    Modifier,
    NounPhrase,
    NounPhraseKind,
    Number,
    Possessor,
    PostModifier,
)
from .context import ParseContext
from .english import EnglishParser
from .grammar import GrammarAnalyzer
from .numeral import is_number_word, numeral_value

_NAME_ENTITIES = frozenset({"GPE", "PERSON", "ORG", "LOC", "FAC", "NORP"})
_NP_DEPS = frozenset(
    {"det", "amod", "compound", "nummod", "quantmod", "poss", "nmod:poss", "prep", "predet"}
    | {"advmod"}
    | {"appos", "conj", "cc", "punct"}
)


def adverb_modifier(child):
    return Modifier(
        child.text,
        child.lemma_.lower(),
        "modifier",
        child.pos_,
        sub_modifiers=[
            Modifier(adv.text, adv.lemma_.lower(), "modifier", adv.pos_, indices=(adv.i,))
            for adv in child.children
            if adv.dep_ == "advmod"
        ],
        indices=(child.i,),
    )


class NounPhraseBuilder:
    def __init__(self, context: ParseContext, build_clause):
        self.context = context
        self.build_clause = build_clause

    @staticmethod
    def _leading_symbols(token):
        symbols: list[Any] = []
        index = token.i - 1
        while index >= 0 and token.doc[index].is_currency:
            symbols.insert(0, token.doc[index])
            index -= 1
        return symbols

    @staticmethod
    def _proper_span(token):
        """First and last token of a multiword proper name headed by `token`, or None."""
        doc = token.doc
        subtree = {item.i for item in token.subtree}
        for entity in doc.ents:
            if entity.start <= token.i < entity.end and entity.label_ in _NAME_ENTITIES:
                start = entity.start
                while start < entity.end and doc[start].pos_ == "DET":
                    start += 1
                if all(i in subtree for i in range(start, entity.end)) and start < entity.end - 1:
                    return start, entity.end - 1
        parts = {
            child.i
            for child in token.children
            if child.pos_ == "PROPN" and child.dep_ in {"compound", "flat", "flat:name", "nmod"}
        }
        left = right = token.i
        while left - 1 in parts:
            left -= 1
        while right + 1 in parts:
            right += 1
        return (left, right) if left != right else None

    def _indices(self, token):
        """The token's index plus any currency symbols fused into its literal text."""
        if not any(char.isdigit() for char in token.text):
            return (token.i,)
        return (*(symbol.i for symbol in self._leading_symbols(token)), token.i)

    def _symbol_text(self, token):
        """Digit tokens keep a leading currency symbol attached, as one literal."""
        if not any(char.isdigit() for char in token.text):
            return EnglishParser.original(token)
        prefix = "".join(
            symbol.text + symbol.whitespace_ for symbol in self._leading_symbols(token)
        )
        return prefix + token.text

    @staticmethod
    def _is_numeral_part(head, child):
        return child.dep_ == "conj" and head.pos_ == "NUM" and child.pos_ == "NUM"

    def build_np(self, token, seen=None):
        seen = set() if seen is None else seen
        if token.i in seen:
            return NounPhrase(
                token.lemma_.lower(), pos=token.pos_, surface=EnglishParser.original(token)
            )
        seen.add(token.i)
        pron_types = set(token.morph.get("PronType"))
        person = GrammarAnalyzer.morph_value(token, "Person", {"1", "2", "3"})
        raw_number = GrammarAnalyzer.morph_value(token, "Number", {"sing", "plur"})
        number_values: dict[str, Number] = {"sing": "singular", "plur": "plural"}
        number = number_values.get(raw_number, UNSPECIFIED)
        np_kind: NounPhraseKind
        demonstrative: Demonstrative
        if "Dem" in pron_types:
            np_kind = "demonstrative_pronoun" if token.pos_ == "PRON" else "noun"
            demonstrative = "proximal" if token.lemma_.lower() in {"this", "these"} else "distal"
        elif token.like_num or token.pos_ == "NUM":
            np_kind, demonstrative = "number", "none"
        elif token.pos_ == "PROPN":
            np_kind, demonstrative = "proper", "none"
        elif token.morph.get("Reflex") == ["Yes"]:
            np_kind, demonstrative = "other_pronoun", "none"
        elif "Prs" in pron_types and person in {"1", "2", "3"}:
            np_kind, demonstrative = "pronoun", "none"
        elif pron_types & {"Int", "Rel"} or token.tag_ in {"WP", "WP$", "WDT", "WRB"}:
            np_kind, demonstrative = "wh_pronoun", "none"
        elif pron_types & {"Ind", "Neg", "Tot", "Rcp"} or token.pos_ == "PRON":
            np_kind, demonstrative = "other_pronoun", "none"
        else:
            np_kind, demonstrative = "noun", "none"

        if np_kind in {
            "proper",
            "number",
            "demonstrative_pronoun",
            "wh_pronoun",
            "other_pronoun",
        }:
            definiteness: Definiteness = "none"
            determiner = None
        else:
            determiner = next(
                (
                    child
                    for child in token.children
                    if child.dep_ == "det" and child.morph.get("Definite")
                ),
                None,
            )
            definite = (
                GrammarAnalyzer.morph_value(determiner, "Definite", {"def", "ind"})
                if determiner
                else UNSPECIFIED
            )
            definiteness_values: dict[str, Definiteness] = {
                "def": "definite",
                "ind": "indefinite",
            }
            definiteness = definiteness_values.get(definite, UNSPECIFIED)
            if any(
                child.dep_ in {"poss", "nmod:poss"} or child.morph.get("Poss") == ["Yes"]
                for child in token.children
            ):
                definiteness = UNSPECIFIED
            if any(child.morph.get("PronType") == ["Dem"] for child in token.children):
                definiteness = UNSPECIFIED
        case_values = token.morph.get("Case")
        case = case_values[0].lower() if case_values else UNSPECIFIED
        gender = GrammarAnalyzer.morph_value(token, "Gender", {"masc", "fem", "neut", "com"})
        foreign = {
            item.i
            for child in token.children
            if child.dep_ in {"prep", "relcl", "acl", "appos", "poss", "nmod:poss", "conj"}
            and not self._is_numeral_part(token, child)
            for item in child.subtree
        }
        own_tokens = [item for item in token.subtree if item.i not in foreign]
        number_tokens = [
            item
            for item in own_tokens
            if (parts := item.text.lower().replace("-", " ").split()) and is_number_word(parts[0])
        ]
        digit_tokens = [item for item in own_tokens if any(char.isdigit() for char in item.text)]
        number_value = (
            None
            if digit_tokens
            else numeral_value(item.text for item in sorted(number_tokens, key=lambda item: item.i))
        )
        modifiers: list[Modifier] = []
        name_span = self._proper_span(token) if np_kind == "proper" else None
        predeterminers = [
            Modifier(
                child.text, child.lemma_.lower(), "predeterminer", child.pos_, indices=(child.i,)
            )
            for child in sorted(token.children, key=lambda item: item.i)
            if child.dep_ == "predet"
        ]
        adverbs = [
            adverb_modifier(child)
            for child in sorted(token.children, key=lambda item: item.i)
            if child.dep_ == "advmod"
        ]
        demonstrative_index = token.i if np_kind == "demonstrative_pronoun" else None
        for symbol in token.children:
            following = token.doc[symbol.i + 1] if symbol.i + 1 < len(token.doc) else None
            attached = (
                following is not None
                and any(char.isdigit() for char in following.text)
                and symbol.i in {child.i for child in self._leading_symbols(following)}
            )
            if symbol.pos_ == "SYM" and symbol.i < token.i and not attached:
                modifiers.append(
                    Modifier(
                        symbol.text,
                        symbol.lemma_.lower(),
                        "modifier",
                        symbol.pos_,
                        None,
                        True,
                        indices=(symbol.i,),
                    )
                )
        for child in sorted(token.children, key=lambda item: item.i):
            if child.pos_ == "SYM":
                continue
            if name_span is not None and name_span[0] <= child.i <= name_span[1]:
                continue
            if child in number_tokens and child is not token:
                if (
                    child.text.lower() not in {"a", "and"}
                    and np_kind != "number"
                    and not any(modifier.kind == "numeral" for modifier in modifiers)
                ):
                    numeral_text = " ".join(item.text for item in number_tokens)
                    modifiers.append(
                        Modifier(
                            numeral_text,
                            numeral_text.lower(),
                            "numeral",
                            "NUM",
                            number_value,
                            indices=tuple(item.i for item in number_tokens),
                        )
                    )
                continue
            if child.dep_ == "det" and child.morph.get("PronType") == ["Dem"]:
                demonstrative = (
                    "proximal" if child.lemma_.lower() in {"this", "these"} else "distal"
                )
                demonstrative_index = child.i
                continue
            if child.dep_ not in {"amod", "compound", "nummod", "quantmod", "det", "poss"}:
                continue
            if child.dep_ == "det" and (
                child.morph.get("Definite") or child.text.lower() in {"a", "an", "the"}
            ):
                continue
            if child.dep_ == "poss" or child.morph.get("Poss") == ["Yes"]:
                continue
            if child.dep_ in {"nummod", "quantmod"} and child in number_tokens:
                continue
            sub_modifiers = [
                Modifier(adv.text, adv.lemma_.lower(), "modifier", adv.pos_, indices=(adv.i,))
                for adv in child.children
                if adv.dep_ == "advmod"
            ]
            ordinal = "Ord" in child.morph.get("NumType") or child.lemma_.lower() in {
                "first",
                "second",
                "third",
            }
            modifiers.append(
                Modifier(
                    self._symbol_text(child),
                    child.lemma_.lower(),
                    "ordinal" if ordinal else "modifier",
                    child.pos_,
                    None,
                    any(char.isdigit() for char in child.text),
                    sub_modifiers,
                    self._indices(child),
                    GrammarAnalyzer.degree(child),
                )
            )
        for digit_token in digit_tokens:
            if digit_token.i == token.i:
                continue
            if not any(
                modifier.text == self._symbol_text(digit_token) and modifier.literal
                for modifier in modifiers
            ):
                digit_modifier = Modifier(
                    self._symbol_text(digit_token),
                    digit_token.lemma_.lower(),
                    "numeral",
                    digit_token.pos_,
                    None,
                    True,
                    indices=self._indices(digit_token),
                )
                numeral_position = next(
                    (
                        index
                        for index, modifier in enumerate(modifiers)
                        if modifier.kind == "numeral" and modifier.value is None
                    ),
                    len(modifiers),
                )
                modifiers.insert(numeral_position, digit_modifier)

        possessor_token = next(
            (
                child
                for child in token.children
                if child.dep_ in {"poss", "nmod:poss"} or child.morph.get("Poss") == ["Yes"]
            ),
            None,
        )
        possessor = (
            Possessor(self.build_np(possessor_token, seen.copy())) if possessor_token else None
        )
        post_modifiers = []
        for child in token.children:
            if name_span is not None and name_span[0] <= child.i <= name_span[1]:
                continue
            if child.dep_ == "prep":
                pobj = next((item for item in child.children if item.dep_ in {"pobj", "obj"}), None)
                post_modifiers.append(
                    PostModifier(
                        "prep",
                        child.lemma_.lower(),
                        self.build_np(pobj, seen.copy()) if pobj else None,
                        index=child.i,
                    )
                )
            elif child.dep_ in {"relcl", "acl"} and child in self.context.clause_heads:
                linked_clause = self.build_clause(child)
                marker = next(
                    (item for item in child.children if item.dep_ in {"mark", "cc"}), None
                )
                post_modifiers.append(
                    PostModifier(
                        "clause",
                        link=ClauseLink(
                            "complement",
                            self.context.source_for(marker) if marker else None,
                            linked_clause,
                            [
                                self.context.source_for(item)
                                for item in child.subtree
                                if self.context.source_for(item)
                            ],
                        ),
                    )
                )
        coordinated = []
        for child in token.children:
            if child.dep_ == "conj" and not self._is_numeral_part(token, child):
                conjunction = next((item for item in token.children if item.dep_ == "cc"), None)
                coordinated.append(
                    Coordination(
                        self.context.source_for(conjunction) if conjunction else None,
                        self.build_np(child, seen.copy()),
                    )
                )
        if token.pos_ == "PRON" and "Dem" in pron_types:
            person = gender = case = UNSPECIFIED
        if np_kind not in {"pronoun", "wh_pronoun", "other_pronoun"}:
            person = gender = case = UNSPECIFIED
        return NounPhrase(
            head=token.lemma_.lower(),
            kind=np_kind,
            number=number,
            demonstrative=demonstrative,
            person=person,
            gender=gender,
            case=case,
            modifiers=modifiers,
            possessor=possessor,
            post_modifiers=post_modifiers,
            coordinated=coordinated,
            source_tokens=[
                self.context.source_for(item)
                for item in token.subtree
                if self.context.source_for(item)
            ],
            morphology=EnglishParser.morphology(token),
            surface=(
                EnglishParser.span_text(token.doc[name_span[0] : name_span[1] + 1])
                if name_span is not None
                else self._symbol_text(token)
            ),
            pos=token.pos_,
            definiteness=definiteness,
            numeral_value=number_value,
            literal=any(char.isdigit() for char in token.text),
            head_indices=(
                tuple(range(name_span[0], name_span[1] + 1))
                if name_span is not None
                else tuple(item.i for item in number_tokens)
                if np_kind == "number" and number_value is not None
                else self._indices(token)
            ),
            determiner_index=determiner.i if determiner is not None else None,
            demonstrative_index=demonstrative_index,
            predeterminers=predeterminers,
            adverbs=adverbs,
            degree=GrammarAnalyzer.degree(token),
        )

    def is_plain_np(self, token):
        """True when every dependent of the head is something this builder realizes."""
        for child in token.children:
            if child.dep_ not in _NP_DEPS:
                return False
            if child.dep_ in {"appos", "conj"} and not self.is_plain_np(child):
                return False
        return True

    def list_items(self, root):
        items = [root]
        for child in sorted(root.children, key=lambda item: item.i):
            if child.dep_ == "appos":
                items.extend(self.list_items(child))
        return items
