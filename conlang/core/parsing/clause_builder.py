"""Build clauses, arguments, and links from analyzed dependencies."""

from typing import Any

from ..ir import (
    Argument,
    ArgumentRelation,
    Clause,
    ClauseLink,
    ClauseLinkRelation,
    Modifier,
    Polarity,
)
from ..roles import argument_role
from .context import ParseContext
from .grammar import GrammarAnalyzer
from .noun_phrase_builder import NounPhraseBuilder, adverb_modifier


class ClauseBuilder:
    def __init__(self, context: ParseContext):
        self.context = context
        self.cache: dict[int, Clause] = {}
        self.noun_phrases = NounPhraseBuilder(context, self.build_clause)

    def build_clause(self, root, main=False):
        if root.i in self.cache:
            return self.cache[root.i]
        children, voice, tense, perfect, progressive, mood, kind = GrammarAnalyzer.analyze_clause(
            root, self.context.sent, main
        )

        core = [child for child in children if child.dep_ in {"obj", "dobj", "dative", "iobj"}]
        passive_agents: list[Any] = []
        for prep in children:
            if prep.dep_ == "agent" or prep.dep_ == "prep" and prep.lemma_.lower() == "by":
                passive_agents.extend(
                    child for child in prep.children if child.dep_ in {"pobj", "obj"}
                )
        transitive = bool(core or passive_agents or voice == "passive")
        relations: dict[str, ArgumentRelation] = {
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
                np = self.noun_phrases.build_np(head)
                arguments.append(
                    Argument(
                        relation,
                        argument_role(relation, voice, transitive),
                        np,
                        child.dep_,
                        ([self.context.source_for(child)] if head is not child else [])
                        + np.source_tokens,
                        child.lemma_.lower() if head is not child else None,
                        child.i if head is not child else None,
                    )
                )
            elif child.dep_ in {"attr", "acomp"}:
                np = self.noun_phrases.build_np(child)
                arguments.append(Argument("object", "other", np, child.dep_, np.source_tokens))
            elif child.dep_ == "prep":
                for obj in (item for item in child.children if item.dep_ in {"pobj", "obj"}):
                    relation = "indirect_object" if child.lemma_.lower() == "to" else "oblique"
                    np = self.noun_phrases.build_np(obj)
                    arguments.append(
                        Argument(
                            relation,
                            argument_role(relation, voice, transitive),
                            np,
                            "prep",
                            [self.context.source_for(child)] + np.source_tokens,
                            child.lemma_.lower(),
                            child.i,
                        )
                    )
        for token in passive_agents:
            np = self.noun_phrases.build_np(token)
            marker = (
                self.context.source_for(token.head)
                if token.head.dep_ in {"agent", "prep"}
                else None
            )
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
        negation_heads = {root, *(child for child in children if child.dep_ in {"aux", "auxpass"})}
        polarity: Polarity = (
            "negative"
            if any(child.dep_ == "neg" and child.head in negation_heads for child in root.subtree)
            else "positive"
        )
        adverbs = [adverb_modifier(child) for child in children if child.dep_ == "advmod"]
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
            source_tokens=[
                self.context.source_for(item)
                for item in root.subtree
                if self.context.source_for(item)
            ],
            argument_order=[(argument.relation, argument.np.head) for argument in arguments],
        )
        self.cache[root.i] = clause
        for child in children:
            if child not in self.context.clause_heads or child is root:
                continue
            link_relations: dict[str, ClauseLinkRelation] = {
                "conj": "coordinate",
                "advcl": "adverbial",
                "ccomp": "complement",
                "xcomp": "xcomp",
            }
            link_relation = link_relations.get(child.dep_)
            if link_relation:
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
                        link_relation,
                        self.context.source_for(marker) if marker else None,
                        self.build_clause(child),
                        [
                            self.context.source_for(item)
                            for item in child.subtree
                            if self.context.source_for(item)
                        ],
                    )
                )
        return clause

    def build_fragment(self, root):
        """Build a nominal or interjection clause for input without a verbal root."""
        tokens = list(self.context.source.values())
        if root.pos_ == "INTJ" and all(
            item.pos_ in {"PUNCT", "INTJ"} for item in self.context.sent
        ):
            return Clause(kind="interjection", source_tokens=tokens)
        if root.pos_ not in {"NOUN", "PROPN", "PRON", "NUM"} or not self.noun_phrases.is_plain_np(
            root
        ):
            return None
        arguments = []
        for item in self.noun_phrases.list_items(root):
            np = self.noun_phrases.build_np(item)
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
