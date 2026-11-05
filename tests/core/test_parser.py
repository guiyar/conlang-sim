import pytest
from conftest import PARSER_PROBLEM

from conlang.core.parser import parse, parser_versions

pytestmark = pytest.mark.skipif(
    PARSER_PROBLEM is not None, reason=PARSER_PROBLEM or "pinned parser unavailable"
)


@pytest.mark.parametrize(
    "text",
    [
        "Alice sees Bob.",
        "Bob was seen by Alice.",
        "The window was broken.",
        "The window got broken.",
        "They have eaten.",
        "They have been eating.",
        "We will go.",
        "We won't go.",
        "Did they leave?",
        "Who left?",
        "Open the door.",
        "She is happy.",
        "She is at home.",
        "There is a problem.",
        "I gave her a book.",
        "This dog is friendly.",
        "These are mine.",
        "You are ready.",
        "We are ready.",
        "John's cup broke.",
        "A cup of tea is here.",
        "The person who called left.",
        "I think she left.",
    ],
)
def test_pinned_parser_fixtures_never_crash(text):
    result = parse(text)[0]
    assert result.source_text == text
    assert result.clause.source_tokens


def test_parser_versions_are_pinned():
    versions = parser_versions()
    assert versions["spacy"].startswith("3.8.")
    assert versions["model"].startswith("3.8.0")


def test_weak_parser_cases_remain_robust():
    for text in ("dogs", "the cat walked", "They have walked.", "!!!"):
        result = parse(text)[0]
        assert result is not None
        if result.clause.kind == "rootless":
            assert result.rules


def test_rootless_fragment_preserves_tokens():
    result = parse("!!!")[0]
    assert result.clause.fragments == [["!", "!", "!"]]


def test_dative_preposition_preserves_indirect_object_np():
    result = parse("Mina gave two books to you.")[0]
    recipient = next(
        argument for argument in result.clause.arguments if argument.relation == "indirect_object"
    )
    assert recipient.np.head == "you"
    assert recipient.np.kind == "pronoun"
    assert recipient.preposition == "to"


def test_voice_roles_tense_aspect_and_mood_derivations():
    active = parse("Alice sees Bob.")[0].clause
    assert active.voice == "active"
    assert active.transitivity
    assert [(argument.relation, argument.role) for argument in active.arguments] == [
        ("subject", "agent"),
        ("object", "patient"),
    ]
    passive = parse("Bob was seen by Alice.")[0].clause
    assert passive.voice == "passive"
    assert [(argument.relation, argument.role) for argument in passive.arguments] == [
        ("subject", "patient"),
        ("oblique", "agent"),
    ]
    perfect = parse("They have eaten.")[0].clause
    progressive_perfect = parse("They have been eating.")[0].clause
    assert (perfect.perfect, perfect.progressive) == (True, False)
    assert (progressive_perfect.perfect, progressive_perfect.progressive) == (True, True)
    assert parse("We won't go.")[0].clause.tense == "future"
    assert parse("They might go.")[0].clause.tense == "UNSPECIFIED"
    assert parse("Did they leave?")[0].clause.mood == "interrogative"
    assert parse("Open the door.")[0].clause.mood == "imperative"


def test_clause_kinds_pronoun_number_demonstratives_and_possession():
    assert parse("She is happy.")[0].clause.kind == "equational"
    assert parse("She is at home.")[0].clause.kind == "locative"
    assert parse("There is a problem.")[0].clause.kind == "existential"
    you = parse("You are ready.")[0].clause.arguments[0].np
    we = parse("We are ready.")[0].clause.arguments[0].np
    assert (you.person, you.number) == ("2", "UNSPECIFIED")
    assert (we.person, we.number) == ("1", "plural")
    demonstrative = parse("These are mine.")[0].clause.arguments[0].np
    assert demonstrative.kind == "demonstrative_pronoun"
    assert demonstrative.demonstrative == "proximal"
    assert demonstrative.number == "plural"
    possessive = parse("John's cup broke.")[0].clause.arguments[0].np
    of_phrase = parse("A cup of tea is here.")[0].clause.arguments[0].np
    assert possessive.possessor.np.surface == "John"
    assert of_phrase.possessor is None
    assert any(item.kind == "prep" and item.adposition == "of" for item in of_phrase.post_modifiers)


def test_embedded_clause_is_retained_as_link():
    result = parse("I think she left.")[0]
    assert result.clause.links
    assert result.clause.links[0].relation == "complement"


def test_coordinated_np_and_numeral_modifier_are_preserved():
    coordinated = parse("Alice and Bob left.")[0].clause.arguments[0].np
    assert coordinated.head == "alice"
    assert [item.np.head for item in coordinated.coordinated] == ["bob"]
    numeral_np = parse("Two dogs ran.")[0].clause.arguments[0].np
    numeral = next(modifier for modifier in numeral_np.modifiers if modifier.kind == "numeral")
    assert numeral.text == "Two"


@pytest.mark.parametrize(
    "text, tense, voice, mood, kind, arguments",
    [
        (
            "Alice sees Bob.",
            "present",
            "active",
            "declarative",
            "verbal",
            [("subject", "agent"), ("object", "patient")],
        ),
        (
            "Bob was seen by Alice.",
            "past",
            "passive",
            "declarative",
            "verbal",
            [("subject", "patient"), ("oblique", "agent")],
        ),
        (
            "The window was broken.",
            "past",
            "passive",
            "declarative",
            "verbal",
            [("subject", "patient")],
        ),
        (
            "The window got broken.",
            "past",
            "passive",
            "declarative",
            "verbal",
            [("subject", "patient")],
        ),
        ("They have eaten.", "present", "active", "declarative", "verbal", [("subject", "other")]),
        (
            "They have been eating.",
            "present",
            "active",
            "declarative",
            "verbal",
            [("subject", "other")],
        ),
        ("We will go.", "future", "active", "declarative", "verbal", [("subject", "other")]),
        ("We won't go.", "future", "active", "declarative", "verbal", [("subject", "other")]),
        ("Did they leave?", "past", "active", "interrogative", "verbal", [("subject", "other")]),
        ("Who left?", "past", "active", "interrogative", "verbal", [("subject", "other")]),
        (
            "Open the door.",
            "UNSPECIFIED",
            "active",
            "imperative",
            "verbal",
            [("object", "patient")],
        ),
        (
            "She is happy.",
            "present",
            "active",
            "declarative",
            "equational",
            [("subject", "other"), ("object", "other")],
        ),
        (
            "She is at home.",
            "present",
            "active",
            "declarative",
            "locative",
            [("subject", "other"), ("oblique", "other")],
        ),
        (
            "There is a problem.",
            "present",
            "active",
            "declarative",
            "existential",
            [("object", "other")],
        ),
        (
            "I gave her a book.",
            "past",
            "active",
            "declarative",
            "verbal",
            [("subject", "agent"), ("indirect_object", "other"), ("object", "patient")],
        ),
    ],
)
def test_pinned_parser_fixtures_assert_derivations(text, tense, voice, mood, kind, arguments):
    clause = parse(text)[0].clause
    assert (clause.tense, clause.voice, clause.mood, clause.kind) == (tense, voice, mood, kind)
    assert [(argument.relation, argument.role) for argument in clause.arguments] == arguments


def test_pinned_parser_fixture_fields_keep_pos_definiteness_numerals_and_structured_possession():
    definite = parse("The red dog ran.")[0].clause.arguments[0].np
    indefinite = parse("A dog ran.")[0].clause.arguments[0].np
    adjective = parse("She is happy.")[0].clause.arguments[1].np
    possessor = parse("John's red cup broke.")[0].clause.arguments[0].np.possessor
    post_modifier = parse("A cup of tea broke.")[0].clause.arguments[0].np.post_modifiers[0]
    numeral = parse("Three hundred and five birds flew.")[0].clause.arguments[0].np
    assert (definite.definiteness, indefinite.definiteness) == ("definite", "indefinite")
    assert adjective.pos == "ADJ"
    assert possessor.np.pos == "PROPN"
    assert post_modifier.kind == "prep" and post_modifier.adposition == "of"
    assert numeral.numeral_value == 305
    assert parse("Who left?")[0].clause.arguments[0].np.kind == "wh_pronoun"


def test_negation_belongs_to_the_clause_it_modifies():
    main = parse("I think he didn't leave.")[0].clause
    assert main.polarity == "positive"
    assert main.links[0].clause.polarity == "negative"
    for text in ("He didn't leave.", "He has not eaten.", "He never eats.", "Don't eat."):
        assert parse(text)[0].clause.polarity == "negative", text
    assert parse("He left.")[0].clause.polarity == "positive"


def test_only_matrix_wh_words_make_a_question():
    for text in ("I know where he went.", "The man who called left.", "She asked what he ate."):
        assert parse(text)[0].clause.mood == "declarative", text
    for text in ("Where did he go?", "Who left?", "What do you want?", "Which dog ate?"):
        assert parse(text)[0].clause.mood == "interrogative", text


def test_currency_symbols_fuse_into_the_number_literal():
    def literals(text):
        argument = next(a for a in parse(text)[0].clause.arguments if a.relation == "object")
        return argument.np.surface, [m.text for m in argument.np.modifiers if m.literal]

    assert literals("It costs $5.")[0] == "$5"
    assert literals("It costs € 5.")[0] == "€ 5"
    assert literals("It costs 5 dollars.")[0] == "dollars"


def test_degree_comes_from_morphology():
    arguments = parse("The dog is bigger.")[0].clause.arguments
    assert any(a.np.degree == "comparative" for a in arguments)
    arguments = parse("The cat is the biggest.")[0].clause.arguments
    assert any(a.np.degree == "superlative" for a in arguments)
