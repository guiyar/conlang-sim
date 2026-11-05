"""spaCy boundary: parse English and immediately convert to language-neutral IR."""

from typing import Any

from .ir import (
    UNSPECIFIED,
    Argument,
    Clause,
    ClauseLink,
    Coordination,
    Modifier,
    NounPhrase,
    Possessor,
    PostModifier,
    SentenceIR,
)
from .parsing.english import EnglishParser
from .parsing.grammar import GrammarAnalyzer
from .parsing.numeral import is_number_word, numeral_value
from .parsing.token_ledger import TokenLedger
from .results import info
from .roles import argument_role

MODEL_NAME = EnglishParser.MODEL_NAME
MODEL_VERSION = EnglishParser.MODEL_VERSION
_model = EnglishParser.model
_is_all_caps = EnglishParser.is_all_caps
_analyze = EnglishParser.analyze
_original = EnglishParser.original
_span_text = EnglishParser.span_text


_morph = EnglishParser.morphology


def parser_versions():
    return EnglishParser.versions()


def _revision_number_value(tokens):
    return numeral_value(token.text for token in sorted(tokens, key=lambda item: item.i))


def fallback_source(text):
    """Source tokens and CARDINAL spans for text that never reached the sentence parser."""
    doc = _analyze(text)
    ledger = TokenLedger(doc)
    return list(ledger.source.values()), ledger.numeral_spans


def _adverb(child):
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


_NAME_ENTITIES = frozenset({"GPE", "PERSON", "ORG", "LOC", "FAC", "NORP"})
_NP_DEPS = frozenset(
    {"det", "amod", "compound", "nummod", "quantmod", "poss", "nmod:poss", "prep", "predet"}
    | {"advmod"}
    | {"appos", "conj", "cc", "punct"}
)


class _SentenceBuilder:
    """Builds IR clauses and noun phrases for one spaCy sentence."""

    def __init__(self, sent):
        self.sent = sent
        self.ledger = TokenLedger(sent)
        self.source = self.ledger.source
        self.clause_heads = {token for token in sent if GrammarAnalyzer.is_clause_head(token)}
        self.cache = {}
        self.numeral_spans = self.ledger.numeral_spans

    def source_for(self, token):
        return self.ledger.source_for(token)

    @staticmethod
    def _leading_symbols(token):
        symbols: list = []
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
        for ent in doc.ents:
            if ent.start <= token.i < ent.end and ent.label_ in _NAME_ENTITIES:
                start = ent.start
                while start < ent.end and doc[start].pos_ == "DET":
                    start += 1
                if all(i in subtree for i in range(start, ent.end)) and start < ent.end - 1:
                    return start, ent.end - 1
        parts = {
            c.i
            for c in token.children
            if c.pos_ == "PROPN" and c.dep_ in {"compound", "flat", "flat:name", "nmod"}
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
            return _original(token)
        prefix = "".join(c.text + c.whitespace_ for c in self._leading_symbols(token))
        return prefix + token.text

    @staticmethod
    def _is_numeral_part(head, child):
        return child.dep_ == "conj" and head.pos_ == "NUM" and child.pos_ == "NUM"

    def build_clause(self, root, main=False):
        if root.i in self.cache:
            return self.cache[root.i]
        children, voice, tense, perfect, progressive, mood, kind = GrammarAnalyzer.analyze_clause(
            root, self.sent, main
        )

        core = [child for child in children if child.dep_ in {"obj", "dobj", "dative", "iobj"}]
        passive_agents: list[Any] = []
        for prep in children:
            if prep.dep_ == "agent" or prep.dep_ == "prep" and prep.lemma_.lower() == "by":
                passive_agents.extend(
                    child for child in prep.children if child.dep_ in {"pobj", "obj"}
                )
        transitive = bool(core or passive_agents or voice == "passive")
        relations = {
            "nsubj": "subject",
            "nsubjpass": "subject",
            "obj": "object",
            "dobj": "object",
            "dative": "indirect_object",
            "iobj": "indirect_object",
        }
        arguments = []
        for child in children:
            relation = relations.get(child.dep_)
            if relation:
                prep_object = next(
                    (item for item in child.children if item.dep_ in {"pobj", "obj"}), None
                )
                head = prep_object if child.pos_ == "ADP" and prep_object is not None else child
                np = self.build_np(head)
                arguments.append(
                    Argument(
                        relation,
                        argument_role(relation, voice, transitive),
                        np,
                        child.dep_,
                        ([self.source_for(child)] if head is not child else []) + np.source_tokens,
                        child.lemma_.lower() if head is not child else None,
                        child.i if head is not child else None,
                    )
                )
            elif child.dep_ in {"attr", "acomp"}:
                np = self.build_np(child)
                arguments.append(Argument("object", "other", np, child.dep_, np.source_tokens))
            elif child.dep_ == "prep":
                for obj in (item for item in child.children if item.dep_ in {"pobj", "obj"}):
                    relation = "indirect_object" if child.lemma_.lower() == "to" else "oblique"
                    np = self.build_np(obj)
                    arguments.append(
                        Argument(
                            relation,
                            argument_role(relation, voice, transitive),
                            np,
                            "prep",
                            [self.source_for(child)] + np.source_tokens,
                            child.lemma_.lower(),
                            child.i,
                        )
                    )
        for token in passive_agents:
            np = self.build_np(token)
            marker = self.source_for(token.head) if token.head.dep_ in {"agent", "prep"} else None
            arguments.append(
                Argument(
                    "oblique",
                    "agent",
                    np,
                    "by_phrase",
                    ([marker] if marker is not None else []) + np.source_tokens,
                    "by",
                    token.head.i if marker is not None else None,
                )
            )
        negation_heads = {root, *(c for c in children if c.dep_ in {"aux", "auxpass"})}
        polarity = (
            "negative"
            if any(c.dep_ == "neg" and c.head in negation_heads for c in root.subtree)
            else "positive"
        )
        adverbs = [_adverb(child) for child in children if child.dep_ == "advmod"]
        modals = [
            Modifier(child.text, child.lemma_.lower(), "modal", child.pos_, indices=(child.i,))
            for child in children
            if child.dep_ == "aux"
            and child.tag_ == "MD"
            and child.lemma_.lower() not in GrammarAnalyzer.NOT_MODAL
        ]
        clause = Clause(
            predicate=root.lemma_.lower(),
            predicate_pos=root.pos_,
            predicate_index=root.i,
            modals=modals,
            kind=kind,
            polarity=polarity,
            tense=tense,
            perfect=perfect,
            progressive=progressive,
            mood=mood,
            transitivity=transitive,
            voice=voice,
            arguments=arguments,
            adverbs=adverbs,
            source_tokens=[self.source_for(item) for item in root.subtree if self.source_for(item)],
            argument_order=[(argument.relation, argument.np.head) for argument in arguments],
        )
        self.cache[root.i] = clause
        for child in children:
            if child not in self.clause_heads or child is root:
                continue
            relation = {
                "conj": "coordinate",
                "advcl": "adverbial",
                "ccomp": "complement",
                "xcomp": "xcomp",
            }.get(child.dep_)
            if relation:
                marker = next(
                    (item for item in child.children if item.dep_ in {"mark", "cc"}), None
                )
                if marker is None and child.dep_ == "conj":
                    marker = next((item for item in children if item.dep_ == "cc"), None)
                if marker is None and child.dep_ == "xcomp":
                    marker = next(
                        (item for item in child.children if item.lemma_.lower() == "to"), None
                    )
                clause.links.append(
                    ClauseLink(
                        relation,
                        self.source_for(marker) if marker else None,
                        self.build_clause(child),
                        [self.source_for(item) for item in child.subtree if self.source_for(item)],
                    )
                )
        return clause

    def build_np(self, token, seen=None):
        seen = set() if seen is None else seen
        if token.i in seen:
            return NounPhrase(token.lemma_.lower(), pos=token.pos_, surface=_original(token))
        seen.add(token.i)
        pron_types = set(token.morph.get("PronType"))
        person = GrammarAnalyzer.morph_value(token, "Person", {"1", "2", "3"})
        raw_number = GrammarAnalyzer.morph_value(token, "Number", {"sing", "plur"})
        number = {"sing": "singular", "plur": "plural"}.get(raw_number, UNSPECIFIED)
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
            definiteness = "none"
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
            definiteness = {"def": "definite", "ind": "indefinite"}.get(definite, UNSPECIFIED)
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
        numeral_value = None if digit_tokens else _revision_number_value(number_tokens)
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
            _adverb(child)
            for child in sorted(token.children, key=lambda item: item.i)
            if child.dep_ == "advmod"
        ]
        demonstrative_index = token.i if np_kind == "demonstrative_pronoun" else None
        for symbol in token.children:
            following = token.doc[symbol.i + 1] if symbol.i + 1 < len(token.doc) else None
            attached = (
                following is not None
                and any(char.isdigit() for char in following.text)
                and symbol.i in {c.i for c in self._leading_symbols(following)}
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
                    and not any(m.kind == "numeral" for m in modifiers)
                ):
                    numeral_text = " ".join(item.text for item in number_tokens)
                    modifiers.append(
                        Modifier(
                            numeral_text,
                            numeral_text.lower(),
                            "numeral",
                            "NUM",
                            numeral_value,
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
            elif child.dep_ in {"relcl", "acl"} and child in self.clause_heads:
                linked_clause = self.build_clause(child)
                marker = next(
                    (item for item in child.children if item.dep_ in {"mark", "cc"}), None
                )
                post_modifiers.append(
                    PostModifier(
                        "clause",
                        link=ClauseLink(
                            "complement",
                            self.source_for(marker) if marker else None,
                            linked_clause,
                            [
                                self.source_for(item)
                                for item in child.subtree
                                if self.source_for(item)
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
                        self.source_for(conjunction) if conjunction else None,
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
                self.source_for(item) for item in token.subtree if self.source_for(item)
            ],
            morphology=_morph(token),
            surface=(
                _span_text(token.doc[name_span[0] : name_span[1] + 1])
                if name_span is not None
                else self._symbol_text(token)
            ),
            pos=token.pos_,
            definiteness=definiteness,
            numeral_value=numeral_value,
            literal=any(char.isdigit() for char in token.text),
            head_indices=(
                tuple(range(name_span[0], name_span[1] + 1))
                if name_span is not None
                else tuple(item.i for item in number_tokens)
                if np_kind == "number" and numeral_value is not None
                else self._indices(token)
            ),
            determiner_index=determiner.i if determiner is not None else None,
            demonstrative_index=demonstrative_index,
            predeterminers=predeterminers,
            adverbs=adverbs,
            degree=GrammarAnalyzer.degree(token),
        )

    def _is_plain_np(self, token):
        """True when every dependent of the head is something the NP builder realizes."""
        for child in token.children:
            if child.dep_ not in _NP_DEPS:
                return False
            if child.dep_ in {"appos", "conj"} and not self._is_plain_np(child):
                return False
        return True

    def _list_items(self, root):
        items = [root]
        for child in sorted(root.children, key=lambda item: item.i):
            if child.dep_ == "appos":
                items.extend(self._list_items(child))
        return items

    def build_fragment(self, root):
        """Build a nominal or interjection clause for input without a verbal root."""
        tokens = list(self.source.values())
        if root.pos_ == "INTJ" and all(item.pos_ in {"PUNCT", "INTJ"} for item in self.sent):
            return Clause(kind="interjection", source_tokens=tokens)
        if root.pos_ not in {"NOUN", "PROPN", "PRON", "NUM"} or not self._is_plain_np(root):
            return None
        arguments = []
        for item in self._list_items(root):
            np = self.build_np(item)
            owned = {
                token.i
                for child in item.children
                if child.dep_ == "appos"
                for token in child.subtree
            }
            np.source_tokens = [
                token
                for token in np.source_tokens
                if token.index is None or token.index not in owned
            ]
            arguments.append(Argument("fragment", "other", np, item.dep_, np.source_tokens))
        return Clause(
            kind="nominal",
            arguments=arguments,
            source_tokens=tokens,
            argument_order=[(argument.relation, argument.np.head) for argument in arguments],
        )


def parse(text):
    """Return one SentenceIR per sentence, preserving linked verbal heads."""
    if not text or not text.strip():
        return []
    doc = _analyze(text)
    sentences = []
    for sent in doc.sents:
        builder = _SentenceBuilder(sent)
        source = builder.source
        main_root = sent.root
        clause_heads = builder.clause_heads
        root_fallback = False
        if main_root not in clause_heads and clause_heads:
            main_root = min(clause_heads, key=lambda token: (token.i, token.dep_ == "relcl"))
            root_fallback = True
        if main_root not in clause_heads:
            fragment_clause = builder.build_fragment(main_root)
            if fragment_clause is not None:
                sentences.append(
                    SentenceIR(
                        fragment_clause,
                        _span_text(sent),
                        [],
                        [],
                        list(source.values()),
                        builder.numeral_spans,
                    )
                )
                continue
            fragment = [[_original(token) for token in sent]]
            clause = Clause(
                kind="rootless", fragments=fragment, source_tokens=list(source.values())
            )
            sentences.append(
                SentenceIR(
                    clause,
                    _span_text(sent),
                    ["No verbal or be root found; source tokens use conlang lexical fallback."],
                    fragment,
                    list(source.values()),
                    builder.numeral_spans,
                )
            )
            continue
        clause = builder.build_clause(main_root, not root_fallback)
        rules = []
        if root_fallback:
            rules.append(
                "The parser root was non-verbal; the available verbal head was realized and remaining tokens retained."
            )
        if any(token.dep_ in {"relcl", "acl", "ccomp", "xcomp", "advcl", "conj"} for token in sent):
            rules.append(
                info(
                    "Embedded and coordinated clauses use profile grammar; relative-clause gaps are simplified."
                )
            )
        sentences.append(
            SentenceIR(
                clause, _span_text(sent), rules, [], list(source.values()), builder.numeral_spans
            )
        )
    return sentences
