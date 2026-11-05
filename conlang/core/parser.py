"""spaCy boundary: parse English and immediately convert to language-neutral IR."""

from functools import lru_cache
from types import MappingProxyType
from .ir import (
    Argument, Clause, ClauseLink, Coordination, Modifier, NounPhrase, Possessor,
    PostModifier, SentenceIR, SourceToken, UNSPECIFIED,
)
from .roles import argument_role

MODEL_NAME = "en_core_web_sm"
MODEL_VERSION = "3.8.0"


@lru_cache(maxsize=1)
def _model():
    try:
        import spacy
        nlp = spacy.load(MODEL_NAME)
    except Exception as error:
        raise RuntimeError("English parser unavailable. Install with: python -m spacy download en_core_web_sm-3.8.0") from error
    if nlp.meta.get("version") != MODEL_VERSION:
        raise RuntimeError(f"Expected {MODEL_NAME} {MODEL_VERSION}, found {nlp.meta.get('version')}. Install with: python -m spacy download en_core_web_sm-3.8.0")
    return nlp


def _morph(token):
    return {key: tuple(value.split(",")) for key, value in token.morph.to_dict().items()}


def _morph_value(token, key, allowed):
    values = token.morph.get(key)
    return values[0].lower() if values and values[0].lower() in allowed else UNSPECIFIED


def parser_versions():
    import importlib.metadata
    try:
        spacy_version = importlib.metadata.version("spacy")
    except importlib.metadata.PackageNotFoundError:
        spacy_version = "missing"
    try:
        model_version = importlib.metadata.version("en-core-web-sm")
    except importlib.metadata.PackageNotFoundError:
        model_version = "missing"
    return {"spacy": spacy_version, "model": model_version}


_ONES = MappingProxyType({
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
})
_TENS = MappingProxyType({
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
})
_NUMBER_WORDS = frozenset(_ONES) | frozenset(_TENS) | {"hundred", "thousand", "million", "billion", "and", "a"}


def _revision_source_token(token):
    return SourceToken(
        token.text, token.lemma_, token.pos_, token.tag_, token.dep_, _morph(token),
        token.head.i, token.i,
    )


def _revision_number_value(tokens):
    words = []
    for token in sorted(tokens, key=lambda item: item.i):
        words.extend(part for part in token.text.lower().replace("-", " ").split() if part in _NUMBER_WORDS)
    if not any(word in _ONES or word in _TENS or word in {"hundred", "thousand", "million", "billion"} for word in words):
        return None
    total = current = 0
    for word in words:
        if word in {"and", "a"}:
            continue
        if word in _ONES:
            current += _ONES[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == "hundred":
            current = max(current, 1) * 100
        else:
            scale = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}[word]
            total += max(current, 1) * scale
            current = 0
    value = total + current
    return value if 0 <= value < 1_000_000_000 else None


def _revision_clause_head(token):
    if token.dep_ in {"aux", "auxpass"}:
        return False
    return token.pos_ == "VERB" or token.lemma_.lower() == "be" and token.pos_ in {"AUX", "VERB"}


def _revision_mood_tam_kind(root, sentence, main):
    children = list(root.children)
    voice = "passive" if any(child.dep_ == "nsubjpass" for child in children) else "active"
    auxiliaries = [child for child in children if child.dep_ in {"aux", "auxpass"}]
    finite = next((child for child in auxiliaries if child.morph.get("VerbForm") == ["Fin"]), root)
    has_will = any(child.lemma_.lower() == "will" or child.text.lower() == "wo" for child in auxiliaries)
    tense = "future" if has_will else UNSPECIFIED
    if not has_will and finite.tag_ != "MD" and finite.morph.get("VerbForm") == ["Fin"]:
        raw = _morph_value(finite, "Tense", {"past", "pres"})
        tense = {"past": "past", "pres": "present"}.get(raw, UNSPECIFIED)
    has_have = any(child.lemma_.lower() == "have" for child in auxiliaries)
    perfect_be = any(child.lemma_.lower() == "be" and child.tag_ == "VBN" for child in auxiliaries)
    perfect = has_have and (root.tag_ == "VBN" or root.tag_ == "VBG" and perfect_be)
    progressive = root.tag_ == "VBG" and any(child.lemma_.lower() == "be" for child in auxiliaries)
    subject = next((child for child in children if child.dep_ in {"nsubj", "nsubjpass"}), None)
    inversion = bool(subject and (root.i < subject.i or any(aux.i < subject.i for aux in auxiliaries)))
    interrogative = main and (
        sentence.text.rstrip().endswith("?") or inversion
        or any(token.tag_ in {"WP", "WRB", "WDT"} for token in sentence)
    )
    imperative = main and root.tag_ == "VB" and subject is None and not auxiliaries and not interrogative
    mood = "interrogative" if interrogative else "imperative" if imperative else "declarative"
    if root.lemma_.lower() == "be":
        kind = "existential" if any(child.dep_ == "expl" for child in children) else (
            "equational" if any(child.dep_ in {"attr", "acomp"} for child in children) else
            "locative" if any(child.dep_ == "prep" for child in children) else "equational"
        )
    else:
        kind = "verbal"
    return children, voice, tense, perfect, progressive, mood, kind


def parse(text):
    """Return one SentenceIR per sentence, preserving linked verbal heads."""
    if not text or not text.strip():
        return []
    doc = _model()(text)
    sentences = []
    for sent in doc.sents:
        source = {token.i: _revision_source_token(token) for token in sent}
        main_root = sent.root
        clause_heads = {token for token in sent if _revision_clause_head(token)}

        def source_for(token):
            return source.get(token.i)

        def build_clause(root, main=False, cache=None):
            cache = {} if cache is None else cache
            if root.i in cache:
                return cache[root.i]
            children, voice, tense, perfect, progressive, mood, kind = _revision_mood_tam_kind(root, sent, main)

            def build_np(token, seen=None):
                seen = set() if seen is None else seen
                if token.i in seen:
                    return NounPhrase(token.lemma_.lower(), pos=token.pos_, surface=token.text)
                seen.add(token.i)
                pron_types = set(token.morph.get("PronType"))
                person = _morph_value(token, "Person", {"1", "2", "3"})
                raw_number = _morph_value(token, "Number", {"sing", "plur"})
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

                if np_kind in {"proper", "number", "demonstrative_pronoun", "wh_pronoun", "other_pronoun"}:
                    definiteness = "none"
                else:
                    determiner = next((child for child in token.children if child.dep_ == "det" and child.morph.get("Definite")), None)
                    definite = _morph_value(determiner, "Definite", {"def", "ind"}) if determiner else UNSPECIFIED
                    definiteness = {"def": "definite", "ind": "indefinite"}.get(definite, UNSPECIFIED)
                    if any(child.dep_ in {"poss", "nmod:poss"} or child.morph.get("Poss") == ["Yes"] for child in token.children):
                        definiteness = UNSPECIFIED
                    if any(child.morph.get("PronType") == ["Dem"] for child in token.children):
                        definiteness = UNSPECIFIED
                case_values = token.morph.get("Case")
                case = case_values[0].lower() if case_values else UNSPECIFIED
                gender = _morph_value(token, "Gender", {"masc", "fem", "neut", "com"})
                number_tokens = [
                    item for item in token.subtree
                    if (parts := item.text.lower().replace("-", " ").split()) and parts[0] in _NUMBER_WORDS
                ]
                digit_tokens = [item for item in token.subtree if any(char.isdigit() for char in item.text)]
                numeral_value = None if digit_tokens else _revision_number_value(number_tokens)
                modifiers = []
                for child in sorted(token.children, key=lambda item: item.i):
                    if child in number_tokens and child is not token:
                        if child.text.lower() not in {"a", "and"} and not any(m.kind == "numeral" for m in modifiers):
                            numeral_text = " ".join(item.text for item in number_tokens)
                            modifiers.append(Modifier(numeral_text, numeral_text.lower(), "numeral", "NUM", numeral_value))
                        continue
                    if child.dep_ == "det" and child.morph.get("PronType") == ["Dem"]:
                        demonstrative = "proximal" if child.lemma_.lower() in {"this", "these"} else "distal"
                        continue
                    if child.dep_ not in {"amod", "compound", "nummod", "quantmod", "det", "poss"}:
                        continue
                    if child.dep_ == "det" and (child.morph.get("Definite") or child.text.lower() in {"a", "an", "the"}):
                        continue
                    if child.dep_ == "poss" or child.morph.get("Poss") == ["Yes"]:
                        continue
                    if child.dep_ in {"nummod", "quantmod"} and child in number_tokens:
                        continue
                    sub_modifiers = [
                        Modifier(adv.text, adv.lemma_.lower(), "modifier", adv.pos_)
                        for adv in child.children if adv.dep_ == "advmod"
                    ]
                    ordinal = "Ord" in child.morph.get("NumType") or child.lemma_.lower() in {"first", "second", "third"}
                    modifiers.append(Modifier(child.text, child.lemma_.lower(), "ordinal" if ordinal else "modifier",
                                              child.pos_, None, any(char.isdigit() for char in child.text), sub_modifiers))
                for digit_token in digit_tokens:
                    if not any(modifier.text == digit_token.text and modifier.literal for modifier in modifiers):
                        digit_modifier = Modifier(digit_token.text, digit_token.lemma_.lower(), "numeral",
                                                  digit_token.pos_, None, True)
                        numeral_position = next((index for index, modifier in enumerate(modifiers)
                                                 if modifier.kind == "numeral" and modifier.value is None), len(modifiers))
                        modifiers.insert(numeral_position, digit_modifier)

                possessor_token = next((child for child in token.children if child.dep_ in {"poss", "nmod:poss"} or child.morph.get("Poss") == ["Yes"]), None)
                possessor = Possessor(build_np(possessor_token, seen.copy())) if possessor_token else None
                post_modifiers = []
                for child in token.children:
                    if child.dep_ == "prep":
                        pobj = next((item for item in child.children if item.dep_ in {"pobj", "obj"}), None)
                        post_modifiers.append(PostModifier("prep", child.lemma_.lower(), build_np(pobj, seen.copy()) if pobj else None))
                    elif child.dep_ in {"relcl", "acl"} and child in clause_heads:
                        linked_clause = build_clause(child, False, cache)
                        marker = next((item for item in child.children if item.dep_ in {"mark", "cc"}), None)
                        post_modifiers.append(PostModifier("clause", link=ClauseLink(
                            "complement", source_for(marker) if marker else None, linked_clause,
                            [source_for(item) for item in child.subtree if source_for(item)],
                        )))
                coordinated = []
                for child in token.children:
                    if child.dep_ == "conj":
                        conjunction = next((item for item in token.children if item.dep_ == "cc"), None)
                        coordinated.append(Coordination(source_for(conjunction) if conjunction else None,
                                                        build_np(child, seen.copy())))
                if token.pos_ == "PRON" and "Dem" in pron_types:
                    person = gender = case = UNSPECIFIED
                if np_kind not in {"pronoun", "wh_pronoun", "other_pronoun"}:
                    person = gender = case = UNSPECIFIED
                return NounPhrase(
                    head=token.lemma_.lower(), kind=np_kind, number=number, demonstrative=demonstrative,
                    person=person, gender=gender, case=case, modifiers=modifiers, possessor=possessor,
                    post_modifiers=post_modifiers, coordinated=coordinated,
                    source_tokens=[source_for(item) for item in token.subtree if source_for(item)],
                    morphology=_morph(token), surface=token.text, pos=token.pos_,
                    definiteness=definiteness, numeral_value=numeral_value,
                    literal=any(char.isdigit() for char in token.text),
                )

            core = [child for child in children if child.dep_ in {"obj", "dobj", "dative", "iobj"}]
            passive_agents = []
            for prep in children:
                if prep.dep_ == "agent" or prep.dep_ == "prep" and prep.lemma_.lower() == "by":
                    passive_agents.extend(child for child in prep.children if child.dep_ in {"pobj", "obj"})
            transitive = bool(core or passive_agents or voice == "passive")
            relations = {"nsubj": "subject", "nsubjpass": "subject", "obj": "object", "dobj": "object",
                         "dative": "indirect_object", "iobj": "indirect_object"}
            arguments = []
            for child in children:
                relation = relations.get(child.dep_)
                if relation:
                    prep_object = next((item for item in child.children if item.dep_ in {"pobj", "obj"}), None)
                    head = prep_object if child.pos_ == "ADP" and prep_object is not None else child
                    np = build_np(head)
                    arguments.append(Argument(
                        relation, argument_role(relation, voice, transitive), np, child.dep_,
                        ([source_for(child)] if head is not child else []) + np.source_tokens,
                        child.lemma_.lower() if head is not child else None,
                    ))
                elif child.dep_ in {"attr", "acomp"}:
                    np = build_np(child)
                    arguments.append(Argument("object", "other", np, child.dep_, np.source_tokens))
                elif child.dep_ == "prep":
                    for obj in (item for item in child.children if item.dep_ in {"pobj", "obj"}):
                        relation = "indirect_object" if child.lemma_.lower() == "to" else "oblique"
                        np = build_np(obj)
                        arguments.append(Argument(relation, argument_role(relation, voice, transitive), np,
                                                  "prep", [source_for(child)] + np.source_tokens, child.lemma_.lower()))
            for token in passive_agents:
                np = build_np(token)
                marker = source_for(token.head) if token.head.dep_ in {"agent", "prep"} else None
                arguments.append(Argument(
                    "oblique", "agent", np, "by_phrase",
                    ([marker] if marker is not None else []) + np.source_tokens, "by",
                ))
            polarity = "negative" if any(token.lower_ in {"not", "n't"} for token in root.subtree) else "positive"
            adverbs = [Modifier(child.text, child.lemma_.lower(), "modifier", child.pos_)
                       for child in children if child.dep_ == "advmod" and child.lower_ not in {"not", "n't"}]
            clause = Clause(
                predicate=root.lemma_.lower(), predicate_pos=root.pos_, kind=kind, polarity=polarity,
                tense=tense, perfect=perfect, progressive=progressive, mood=mood, transitivity=transitive,
                voice=voice, arguments=arguments, adverbs=adverbs,
                source_tokens=[source_for(item) for item in root.subtree if source_for(item)],
                argument_order=[(argument.relation, argument.np.head) for argument in arguments],
            )
            cache[root.i] = clause
            for child in children:
                if child not in clause_heads or child is root:
                    continue
                relation = {"conj": "coordinate", "advcl": "adverbial", "ccomp": "complement", "xcomp": "xcomp"}.get(child.dep_)
                if relation:
                    marker = next((item for item in child.children if item.dep_ in {"mark", "cc"}), None)
                    if marker is None and child.dep_ == "conj":
                        marker = next((item for item in children if item.dep_ == "cc"), None)
                    if marker is None and child.dep_ == "xcomp":
                        marker = next((item for item in child.children if item.lemma_.lower() == "to"), None)
                    clause.links.append(ClauseLink(
                        relation, source_for(marker) if marker else None, build_clause(child, False, cache),
                        [source_for(item) for item in child.subtree if source_for(item)],
                    ))
            return clause

        root_fallback = False
        if main_root not in clause_heads and clause_heads:
            main_root = min(clause_heads, key=lambda token: (token.i, token.dep_ == "relcl"))
            root_fallback = True
        if main_root not in clause_heads:
            fragment = [[token.text for token in sent]]
            clause = Clause(fragments=fragment, source_tokens=list(source.values()))
            sentences.append(SentenceIR(clause, sent.text, ["No verbal or be root found; source tokens use conlang lexical fallback."],
                                         fragment, list(source.values())))
            continue
        clause = build_clause(main_root, not root_fallback)
        rules = []
        if root_fallback:
            rules.append("The parser root was non-verbal; the available verbal head was realized and remaining tokens retained.")
        if any(token.dep_ in {"relcl", "acl", "ccomp", "xcomp", "advcl", "conj"} for token in sent):
            rules.append("Embedded and coordinated clauses use profile grammar; relative-clause gaps are simplified.")
        sentences.append(SentenceIR(clause, sent.text, rules, [], list(source.values())))
    return sentences