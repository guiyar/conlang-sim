import pytest

from conlang.core.parser import parse, parser_versions
from conlang.core.ir import UNSPECIFIED
from conftest import PARSER_PROBLEM

pytestmark = pytest.mark.skipif(PARSER_PROBLEM is not None, reason=PARSER_PROBLEM or "pinned parser unavailable")


@pytest.mark.parametrize("text", [
    "Alice sees Bob.", "Bob was seen by Alice.", "The window was broken.", "The window got broken.",
    "They have eaten.", "They have been eating.", "We will go.", "We won't go.", "Did they leave?",
    "Who left?", "Open the door.", "She is happy.", "She is at home.", "There is a problem.",
    "I gave her a book.", "This dog is friendly.", "These are mine.", "You are ready.", "We are ready.",
    "John's cup broke.", "A cup of tea is here.", "The person who called left.", "I think she left."
])
def test_pinned_parser_fixtures_never_crash(text):
    result = parse(text)
    assert result.source_text == text
    assert result.clause.source_tokens


def test_parser_versions_are_pinned():
    versions = parser_versions()
    assert versions["spacy"].startswith("3.8.")
    assert versions["model"].startswith("3.8.0")


def test_weak_parser_cases_remain_robust():
    for text in ("dogs", "the cat walked", "They have walked.", "!!!"):
        result = parse(text)
        assert result is not None
        if not result.clause.predicate:
            assert result.rules


def test_rootless_fragment_preserves_tokens():
    result = parse("!!!")
    assert result.clause.fragments == [["!", "!", "!"]]


def test_dative_preposition_preserves_indirect_object_np():
    result = parse("Mina gave two books to you.")
    recipient = next(argument for argument in result.clause.arguments if argument.relation == "indirect_object")
    assert recipient.np.head == "you"
    assert recipient.np.kind == "pronoun"
    assert recipient.preposition == "to"


def test_voice_roles_tense_aspect_and_mood_derivations():
    active = parse("Alice sees Bob.").clause
    assert active.voice == "active"
    assert active.transitivity
    assert [(argument.relation, argument.role) for argument in active.arguments] == [("subject", "agent"), ("object", "patient")]
    passive = parse("Bob was seen by Alice.").clause
    assert passive.voice == "passive"
    assert [(argument.relation, argument.role) for argument in passive.arguments] == [("subject", "patient"), ("oblique", "agent")]
    perfect = parse("They have eaten.").clause
    progressive_perfect = parse("They have been eating.").clause
    assert (perfect.perfect, perfect.progressive) == (True, False)
    assert (progressive_perfect.perfect, progressive_perfect.progressive) == (True, True)
    assert parse("We won't go.").clause.tense == "future"
    assert parse("They might go.").clause.tense == "UNSPECIFIED"
    assert parse("Did they leave?").clause.mood == "interrogative"
    assert parse("Open the door.").clause.mood == "imperative"


def test_clause_kinds_pronoun_number_demonstratives_and_possession():
    assert parse("She is happy.").clause.kind == "equational"
    assert parse("She is at home.").clause.kind == "locative"
    assert parse("There is a problem.").clause.kind == "existential"
    you = parse("You are ready.").clause.arguments[0].np
    we = parse("We are ready.").clause.arguments[0].np
    assert (you.person, you.number) == ("2", "UNSPECIFIED")
    assert (we.person, we.number) == ("1", "plural")
    demonstrative = parse("These are mine.").clause.arguments[0].np
    assert demonstrative.kind == "demonstrative_pronoun"
    assert demonstrative.demonstrative == "proximal"
    assert demonstrative.number == "plural"
    possessive = parse("John's cup broke.").clause.arguments[0].np
    of_phrase = parse("A cup of tea is here.").clause.arguments[0].np
    assert possessive.possessor == "John"
    assert of_phrase.possessor is None
    assert "of tea" in of_phrase.post_modifiers


def test_embedded_clause_is_retained_as_fragment():
    result = parse("I think she left.")
    assert result.fragments
    assert any("fragment" in rule.lower() for rule in result.rules)


def test_coordinated_np_and_numeral_modifier_are_preserved():
    coordinated = parse("Alice and Bob left.").clause.arguments[0].np
    assert coordinated.head == "Alice"
    assert [item.head for item in coordinated.coordinated] == ["Bob"]
    numeral_np = parse("Two dogs ran.").clause.arguments[0].np
    numeral = next(modifier for modifier in numeral_np.modifiers if modifier.kind == "numeral")
    assert numeral.text == "Two"