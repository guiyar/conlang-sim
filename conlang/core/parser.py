"""spaCy boundary: parse English and immediately convert to language-neutral IR."""

from functools import lru_cache
from .ir import Argument, Clause, Modifier, NounPhrase, SentenceIR, SourceToken, UNSPECIFIED
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


def _source(doc):
    return [SourceToken(t.text, t.lemma_, t.pos_, t.tag_, t.dep_, _morph(t), t.head.i) for t in doc]


def _morph_value(token, key, allowed):
    values = token.morph.get(key)
    return values[0].lower() if values and values[0].lower() in allowed else UNSPECIFIED


def _np(token):
    pronoun = token.pos_ == "PRON" and token.morph.get("PronType") != ["Dem"]
    demonstrative_token = next((child for child in token.children if child.morph.get("PronType") == ["Dem"]), None)
    demonstrative = "none"
    number = _morph_value(token, "Number", {"sing", "plur"})
    number = {"sing": "singular", "plur": "plural"}.get(number, UNSPECIFIED)
    if token.morph.get("PronType") == ["Dem"]:
        kind = "demonstrative_pronoun" if token.pos_ == "PRON" else "noun"
        demonstrative = "proximal" if token.lemma_.lower() in {"this", "these"} else "distal"
    elif token.like_num:
        kind = "number"
    elif token.pos_ == "PROPN":
        kind = "proper"
    elif pronoun:
        kind = "pronoun"
    else:
        kind = "noun"
    if demonstrative_token is not None:
        demonstrative = "proximal" if demonstrative_token.lemma_.lower() in {"this", "these"} else "distal"
    if token.pos_ == "PRON" and pronoun:
        case_values = token.morph.get("Case")
        case = case_values[0].lower() if case_values else UNSPECIFIED
        person = _morph_value(token, "Person", {"1", "2", "3"})
        gender = _morph_value(token, "Gender", {"masc", "fem", "neut", "com"})
    else:
        case = person = gender = UNSPECIFIED
    modifier_tokens = [child for child in token.children if child.dep_ in {"amod", "compound", "nummod", "det"} and child.morph.get("PronType") != ["Dem"]]
    modifiers = [Modifier(child.text, child.lemma_, "numeral" if child.like_num else "proper" if child.pos_ == "PROPN" else "modifier") for child in modifier_tokens]
    if demonstrative_token is not None and token.pos_ != "PRON":
        modifiers.append(Modifier(demonstrative_token.text, demonstrative_token.lemma_, "demonstrative"))
    if token.pos_ == "PRON" and token.morph.get("PronType") == ["Dem"]:
        modifiers = []
    possessor = next((child.text for child in token.children if child.dep_ in {"poss", "nmod:poss"}), None)
    post = [" ".join(part.text for part in child.subtree) for child in token.children if child.dep_ in {"prep", "relcl", "acl"}]
    coordinated = [_np(child) for child in token.children if child.dep_ == "conj"]
    tokens = [SourceToken(t.text, t.lemma_, t.pos_, t.tag_, t.dep_, _morph(t), t.head.i) for t in token.subtree]
    return NounPhrase(token.lemma_, kind, number, demonstrative, person, gender, case,
                      modifiers=modifiers, possessor=possessor, post_modifiers=post,
                      coordinated=coordinated, source_tokens=tokens, morphology=_morph(token), surface=token.text)


def parse(text):
    doc = _model()(text)
    source_tokens = _source(doc)
    root = next((t for t in doc if t.head == t and (t.pos_ in {"VERB", "AUX"} or t.lemma_.lower() == "be")), None)
    if root is None:
        note = "No verbal or be root found; realized as a source-token fragment."
        fragment = [t.text for t in doc]
        clause = Clause(fragments=[fragment], source_tokens=source_tokens)
        return SentenceIR(clause, text, [note], [fragment])
    children = list(root.children)
    voice = "passive" if any(c.dep_ == "nsubjpass" for c in children) else "active"
    finite = next((c for c in children if c.dep_ in {"aux", "auxpass"} and c.morph.get("VerbForm") == ["Fin"]), root)
    auxiliaries = [c for c in children if c.dep_ in {"aux", "auxpass"}]
    has_will = any(c.lemma_.lower() == "will" or c.text.lower() == "wo" for c in auxiliaries)
    tense = "future" if has_will else UNSPECIFIED
    if not has_will and finite.tag_ != "MD" and finite.morph.get("VerbForm") == ["Fin"]:
        raw_tense = _morph_value(finite, "Tense", {"past", "pres"})
        tense = {"past": "past", "pres": "present"}.get(raw_tense, UNSPECIFIED)
    has_have = any(a.lemma_.lower() == "have" for a in auxiliaries)
    perfect_be = any(a.lemma_.lower() == "be" and a.tag_ == "VBN" for a in auxiliaries)
    perfect = has_have and (root.tag_ == "VBN" or (root.tag_ == "VBG" and perfect_be))
    progressive = root.tag_ == "VBG" and any(a.lemma_.lower() == "be" for a in auxiliaries)
    subject = next((c for c in children if c.dep_ in {"nsubj", "nsubjpass"}), None)
    inversion = bool(subject and (root.i < subject.i or any(a.i < subject.i for a in auxiliaries)))
    interrogative = text.rstrip().endswith("?") or inversion or any(t.tag_ in {"WP", "WRB", "WDT"} for t in doc)
    imperative = root.tag_ == "VB" and subject is None and not auxiliaries and not interrogative
    mood = "interrogative" if interrogative else "imperative" if imperative else "declarative"
    if root.lemma_.lower() == "be":
        if any(c.dep_ == "expl" for c in children):
            kind = "existential"
        elif any(c.dep_ in {"attr", "acomp"} for c in children):
            kind = "equational"
        elif any(c.dep_ == "prep" for c in children):
            kind = "locative"
        else:
            kind = "equational"
    else:
        kind = "verbal"
    core_children = [c for c in children if c.dep_ in {"obj", "dobj", "dative", "iobj"}]
    passive_agent = []
    for prep in children:
        if prep.dep_ == "agent" or (prep.dep_ == "prep" and prep.lemma_.lower() == "by"):
            passive_agent.extend(c for c in prep.children if c.dep_ == "pobj")
    transitive = bool(core_children or passive_agent or voice == "passive")
    args = []
    for token in children:
        dep_to_relation = {"nsubj": "subject", "nsubjpass": "subject", "obj": "object", "dobj": "object", "dative": "indirect_object", "iobj": "indirect_object"}
        relation = dep_to_relation.get(token.dep_)
        if relation:
            prep_object = next((child for child in token.children if token.dep_ == "dative" and token.pos_ == "ADP" and child.dep_ == "pobj"), None)
            head = prep_object or token
            np = _np(head)
            preposition = token.lemma_.lower() if prep_object else None
            args.append(Argument(relation, argument_role(relation, voice, transitive), np, token.dep_, np.source_tokens, preposition))
        elif token.dep_ in {"attr", "acomp"}:
            np = _np(token)
            args.append(Argument("object", "other", np, token.dep_, np.source_tokens))
    for token in passive_agent:
        np = _np(token)
        args.append(Argument("oblique", "agent", np, "by_phrase", np.source_tokens, "by"))
    for prep in children + [grandchild for child in children if child.dep_ in {"attr", "acomp"} for grandchild in child.children]:
        if prep.dep_ == "prep" and prep.lemma_.lower() != "by":
            for pobj in prep.children:
                if pobj.dep_ == "pobj":
                    np = _np(pobj)
                    args.append(Argument("oblique", "other", np, "prep", np.source_tokens, prep.lemma_))
    polarity = "negative" if any(t.dep_ == "neg" or t.lower_ == "not" for t in doc) else "positive"
    clause = Clause(root.lemma_.lower(), root.pos_, kind, polarity, tense, perfect, progressive, mood,
                    transitive, voice, args,
                    [t.lemma_.lower() for t in doc if t.pos_ == "ADV"],
                    source_tokens=source_tokens,
                    argument_order=[(a.relation, a.np.head) for a in args])
    nested = [t for t in doc if t.dep_ in {"ccomp", "relcl", "conj", "advcl", "acl"}]
    rules = []
    fragments = []
    if nested:
        rules.append("Embedded or coordinated clause emitted as a raw-token fragment.")
        fragments = [[t.text for t in item.subtree] for item in nested]
        clause.fragments.extend(fragments)
    return SentenceIR(clause, text, rules, fragments)


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