from dataclasses import fields

from conlang.core.base import Translator
from conlang.core.ir import Clause, Modifier, NounPhrase
from conlang.core.registry import discover_languages
from conlang.core import ir
from conlang.core.parser import parse
from conlang.core.seeds import item_rng
from conlang.languages.austronesian.phonology import Phonology


def test_A0_translate_returns_sentence_list_for_empty_input():
    translator = Translator(discover_languages()["austronesian"], 7)
    assert translator.translate("   ") == []


def test_B0_public_function_and_lexicon_exports():
    translator = Translator(discover_languages()["austronesian"], 7)
    assert isinstance(translator.function_morphs(), dict)
    assert translator.lexicon.export() == []


def test_C1_catalog_has_version_two_articles():
    profile = discover_languages()["austronesian"]
    features = {feature.id for feature in profile.catalog.features}
    assert profile.output_version == 2
    assert {"articles", "article_position"} <= features


def test_I1_I2_I3_ir_preserves_pos_definiteness_and_numerals():
    assert "pos" in {item.name for item in fields(NounPhrase)}
    assert "definiteness" in {item.name for item in fields(NounPhrase)}
    assert "numeral_value" in {item.name for item in fields(NounPhrase)}
    assert {"pos", "value", "sub_modifiers", "literal"} <= {
        item.name for item in fields(Modifier)
    }


def test_I3_digit_modifiers_are_literal_and_keep_source_spelling():
    np = parse("I saw 1,000 birds.")[0].clause.arguments[1].np
    digit = next(modifier for modifier in np.modifiers if modifier.literal)
    assert digit.text == "1,000"
    assert digit.value is None


def test_I4_I6_I7_ir_has_structured_possession_postmodifiers_and_links():
    assert hasattr(ir, "Possessor")
    assert hasattr(ir, "PostModifier")
    assert hasattr(ir, "ClauseLink")
    assert "links" in {item.name for item in fields(Clause)}


def test_I11_parse_returns_one_ir_per_sentence():
    sentences = parse("Alice left. Bob stayed.")
    assert len(sentences) == 2
    assert [sentence.source_text for sentence in sentences] == ["Alice left.", "Bob stayed."]


def test_I2_parser_reads_article_definiteness_from_morphology():
    definite = parse("The dog ran.")[0].clause.arguments[0].np
    indefinite = parse("A dog ran.")[0].clause.arguments[0].np
    unspecified = parse("Many dogs ran.")[0].clause.arguments[0].np
    assert (definite.definiteness, indefinite.definiteness, unspecified.definiteness) == (
        "definite", "indefinite", "UNSPECIFIED"
    )
    assert all(modifier.lemma.lower() not in {"the", "a"} for modifier in definite.modifiers + indefinite.modifiers)


def test_I4_parser_retains_full_possessor_noun_phrase():
    np = parse("John's red cup broke.")[0].clause.arguments[0].np
    assert np.possessor.np.surface == "John"
    assert np.possessor.np.kind == "proper"
    noun_possessor = parse("The old woman's cup broke.")[0].clause.arguments[0].np.possessor.np
    assert noun_possessor.kind == "noun"
    assert noun_possessor.definiteness == "definite"
    assert any(modifier.lemma == "old" for modifier in noun_possessor.modifiers)


def test_I4_possessive_determiner_becomes_source_featured_pronoun_np():
    np = parse("My dog ran.")[0].clause.arguments[0].np
    assert np.possessor.np.kind == "pronoun"
    assert np.possessor.np.person == "1"
    assert np.possessor.np.morphology.get("Poss") == ("Yes",)


def test_I5_parser_distinguishes_wh_and_other_pronouns_without_guessing_person():
    who = parse("Who left?")[0].clause.arguments[0].np
    someone = parse("Someone left.")[0].clause.arguments[0].np
    assert who.kind == "wh_pronoun"
    assert someone.kind == "other_pronoun"
    assert who.person == "UNSPECIFIED"
    reflexive = parse("She hurt herself.")[0].clause.arguments[1].np
    assert reflexive.kind == "other_pronoun"


def test_I6_parser_structures_prepositional_postmodifier():
    np = parse("A cup of tea broke.")[0].clause.arguments[0].np
    assert any(item.kind == "prep" and item.adposition == "of" and item.np.head == "tea" for item in np.post_modifiers)


def test_I7_parser_links_complement_clause_as_clause():
    sentence = parse("I think she left.")[0]
    assert sentence.clause.links
    link = sentence.clause.links[0]
    assert link.relation == "complement"
    assert link.clause.predicate == "leave"


def test_A1_catalog_uses_weighted_austronesian_defaults():
    profile = discover_languages()["austronesian"]
    weighted = {
        feature.id: {option.id: option.weight for option in feature.options}
        for feature in profile.catalog.features
    }
    assert weighted["syllable_structure"] == {"open": 0.70, "closed": 0.25, "closed_clusters": 0.05}
    assert weighted["vowels"] == {"v3": 0.30, "v5": 0.70}
    assert weighted["vowel_length"] == {"none": 0.75, "contrastive": 0.25}
    assert weighted["stop_voicing"] == {"voiceless_only": 0.55, "voiced_and_voiceless": 0.45}
    assert weighted["prenasalized_stops"] == {"no": 0.90, "yes": 0.10}
    assert weighted["glottal_stop"] == {"no": 0.70, "yes": 0.30}
    assert weighted["fricatives"] == {"h": 0.40, "h_s": 0.40, "h_s_f_v": 0.20}
    assert weighted["nasals"] == {"m_n": 0.30, "m_n_ng": 0.50, "m_n_ng_ny": 0.20}
    assert weighted["liquids"] == {"l": 0.30, "r": 0.30, "l_r": 0.40}
    assert weighted["word_initial_vowel"] == {"no": 0.50, "yes": 0.50}
    assert weighted["clause_order"] == {"VSO": 0.30, "VOS": 0.15, "SVO": 0.45, "SOV": 0.10}
    assert weighted["alignment"] == {"symmetrical_voice": 0.25, "active_passive": 0.35, "ergative": 0.15, "plain": 0.25}
    assert weighted["articles"] == {"none": 0.35, "both": 0.30, "definite_only": 0.25, "indefinite_only": 0.10}
    assert weighted["modifier_position"] == {"after": 0.65, "before": 0.35}
    assert weighted["possessor_position"] == {"before": 0.35, "after": 0.65}


def test_A2_codas_and_clusters_are_optional_with_bounded_rates():
    profile = discover_languages()["austronesian"]
    features = profile.catalog.sample(19, {"syllable_structure": "closed_clusters"})
    phonology = Phonology(features, 19, profile.language_id, profile.output_version)
    codas = clusters = 0
    for index in range(1200):
        rng = item_rng(19, profile.language_id, profile.output_version, "test", str(index))
        syllable = phonology.make_syllable(rng)
        segments = phonology.segments(syllable)
        vowel_index = next(i for i, segment in enumerate(segments) if segment in phonology.vowels)
        codas += int(segments[-1] in phonology.codas and len(segments) > vowel_index + 1)
        clusters += int(vowel_index >= 2)
    assert 0.25 < codas / 1200 < 0.45
    assert 0.06 < clusters / 1200 < 0.18


def test_A3_ng_is_coda_eligible_and_ny_is_not():
    profile = discover_languages()["austronesian"]
    features = profile.catalog.sample(31, {"nasals": "m_n_ng_ny"})
    phonology = Phonology(features, 31, profile.language_id, profile.output_version)
    assert "ng" in phonology.codas
    assert "ny" not in phonology.codas
    assert len(phonology.codas) >= 3


def test_A4_phoneme_weights_have_expected_hierarchy_and_seeded_jitter():
    profile = discover_languages()["austronesian"]
    phonology = Phonology(profile.catalog.sample(37, {"vowels": "v5", "vowel_length": "none"}), 37, profile.language_id, profile.output_version)
    vowel_weights = dict(zip(phonology.vowels, phonology.vowel_weights))
    assert vowel_weights["a"] > vowel_weights["e"]
    assert phonology.parameters["phoneme_jitter"]
    assert all(0.5 <= value <= 1.5 for value in phonology.parameters["phoneme_jitter"].values())


def test_A5_root_length_distributions_accept_pos_shape_classes():
    profile = discover_languages()["austronesian"]
    phonology = Phonology(profile.catalog.sample(41), 41, profile.language_id, profile.output_version)
    content = [phonology.make_root(item_rng(41, profile.language_id, profile.output_version, "test", f"content:{i}"), shape="content") for i in range(300)]
    function = [phonology.make_root(item_rng(41, profile.language_id, profile.output_version, "test", f"function:{i}"), shape="function") for i in range(300)]
    assert sum(map(len, content)) / len(content) <= 6.5
    assert sum(map(len, function)) / len(function) <= 2.6


def test_A6_default_sampling_and_rendered_word_lengths_meet_thresholds():
    profile = discover_languages()["austronesian"]
    assignments = [profile.catalog.sample(seed) for seed in range(1000)]
    assert sum(item["syllable_structure"] == "open" for item in assignments) / 1000 >= 0.65
    assert sum(item["syllable_structure"] == "closed_clusters" for item in assignments) / 1000 <= 0.08
    assert sum(item["vowel_length"] == "contrastive" for item in assignments) / 1000 <= 0.35
    sentences = (
        "I will see the dog in the house.", "The children quickly found many birds.",
        "Alice and Bob gave a book to her.", "Where did you go?", "A cup of tea is here.",
        "The red cat was followed by Mina.", "The small dog chased the quick bird.",
        "The old tree stood near the river.",
    )
    passing = []
    for seed in range(150):
        translator = Translator(profile, seed)
        for sentence in sentences:
            translator.translate(sentence)
        entries = translator.lexicon.export()
        content = [len(entry["form"]) for entry in entries if entry["category"] == "lexical" and entry["pos"] != "NUM"]
        functions = [len(entry["form"]) for entry in entries if entry["category"] == "function"]
        passing.append(bool(content) and bool(functions) and sum(content) / len(content) <= 6.0 and sum(functions) / len(functions) <= 2.6)
    assert sum(passing) / len(passing) >= 0.85


def test_A7_five_thousand_generated_surface_words_obey_phonotactics():
    from conlang.core.words import Morpheme, Word

    profile = discover_languages()["austronesian"]
    checked = 0
    for seed in range(200):
        translator = Translator(profile, seed)
        for index in range(25):
            rng = item_rng(seed, profile.language_id, profile.output_version, "acceptance", f"surface:{index}")
            root = translator.phonology.make_root(rng, shape="content")
            word = Word([Morpheme(tuple(translator.phonology.segments(root)), "ROOT", "root")])
            surface = word.surface(translator.phonology.validate_surface, translator.phonology.epenthetic_vowel)
            assert translator.phonology.valid(translator.phonology.segments(surface))
            assert word.segmented().replace("-", "").replace("<", "").replace(">", "") == surface
            checked += 1
    assert checked == 5_000


def test_realization_accepts_every_reachable_fixed_feature_option():
    profile = discover_languages()["austronesian"]
    source = "The very quick dog saw three birds in the garden."
    for feature in profile.catalog.features:
        for option in feature.options:
            assignment = profile.catalog._find({feature.id: option.id}, 0, {})
            fixed = {key: value for key, value in assignment.items() if value is not None}
            translator = Translator(profile, 97, fixed=fixed)
            result = translator.translate(source)[0]
            assert "Unexpected" not in " ".join(result.rules), f"{feature.id}={option.id}"
            for word in result.words:
                surface = word.surface(translator.phonology.validate_surface, translator.phonology.epenthetic_vowel)
                if not word.literal:
                    assert translator.phonology.valid(translator.phonology.segments(surface)), f"{feature.id}={option.id}"


def test_B1_function_forms_are_unique_per_dialect():
    translator = Translator(discover_languages()["austronesian"], 43)
    forms = list(translator.realizer.function_morphs().values())
    assert len(forms) == len(set(forms))


def test_B2_profile_owns_ordered_closed_class_table():
    from conlang.languages.austronesian import profile as profile_module

    table = profile_module.CLOSED_CLASS
    assert isinstance(table, tuple)
    assert all(len(entry) == 2 for entry in table)
    assert ("of", "ADP") in table
    assert ("and", "CCONJ") in table
    assert ("because", "SCONJ") in table
    assert ("very", "ADV") in table


def test_B3_profile_maps_closed_classes_and_numerals_to_word_shapes():
    profile = discover_languages()["austronesian"]
    assert profile.word_shape("DET") == "function"
    assert profile.word_shape("ADP") == "function"
    assert profile.word_shape("AUX") == "function"
    assert profile.word_shape("NUM") == "numeral"
    assert profile.word_shape("NOUN") == "content"


def test_B3_unlisted_closed_class_pos_is_exported_as_function():
    translator = Translator(discover_languages()["austronesian"], 45)
    form = translator.lexicon.root("possessive_particle", "PART")
    entry = next(item for item in translator.lexicon.export() if item["form"] == form)
    assert entry["category"] == "function"
    assert translator.phonology.valid(translator.phonology.segments(form))


def test_C2_article_partition_is_total_and_merge_only():
    from conlang.languages.austronesian.grammar import article_label

    expected = {
        "none": {"definite": None, "indefinite": None, "UNSPECIFIED": None, "none": None},
        "definite_only": {"definite": "DEF", "indefinite": None, "UNSPECIFIED": None, "none": None},
        "indefinite_only": {"definite": None, "indefinite": "INDEF", "UNSPECIFIED": None, "none": None},
        "both": {"definite": "DEF", "indefinite": "INDEF", "UNSPECIFIED": None, "none": None},
    }
    for system, cases in expected.items():
        for definiteness, output in cases.items():
            assert article_label(system, definiteness) == output


def test_D2_numeral_composition_matches_place_value_examples():
    from conlang.languages.austronesian.grammar import numeral_words

    assert numeral_words(0) == ["zero"]
    assert numeral_words(11) == ["ten", "one"]
    assert numeral_words(21) == ["two", "ten", "one"]
    assert numeral_words(100) == ["hundred"]
    assert numeral_words(305) == ["three", "hundred", "five"]
    assert numeral_words(2_500) == ["two", "thousand", "five", "hundred"]
    assert numeral_words(1_000) == ["thousand"]


def test_D3_parser_merges_multiword_cardinal_values():
    np = parse("Three hundred and five birds flew.")[0].clause.arguments[0].np
    numeral = next(modifier for modifier in np.modifiers if modifier.kind == "numeral")
    assert numeral.value == 305
    assert np.numeral_value == 305
    hundred = parse("A hundred birds flew.")[0].clause.arguments[0].np
    ordinary_article = parse("A dog ran.")[0].clause.arguments[0].np
    assert hundred.numeral_value == 100
    assert ordinary_article.numeral_value is None
    hyphenated = parse("Twenty-one birds flew.")[0].clause.arguments[0].np
    hyphenated_modifier = next(modifier for modifier in hyphenated.modifiers if modifier.kind == "numeral")
    assert hyphenated_modifier.value == 21
    unsupported = parse("One billion birds flew.")[0].clause.arguments[0].np
    unsupported_modifier = next(modifier for modifier in unsupported.modifiers if modifier.kind == "numeral")
    assert unsupported_modifier.value is None


def test_D3_unsupported_scale_falls_back_to_individual_num_roots_with_note():
    result = Translator(discover_languages()["austronesian"], 55).translate("One billion birds flew.")[0]
    glosses = [word.gloss() for word in result.words]
    assert "ONE" in glosses and "BILLION" in glosses
    assert any("unparsed numeral" in rule for rule in result.rules)


def test_C3_C4_articles_are_function_morphs_at_the_selected_edge():
    profile = discover_languages()["austronesian"]
    before = Translator(profile, 51, {"articles": "both", "article_position": "before"}).translate("The dog ran.")[0]
    after = Translator(profile, 51, {"articles": "both", "article_position": "after"}).translate("The dog ran.")[0]
    before_glosses = [word.gloss() for word in before.words]
    after_glosses = [word.gloss() for word in after.words]
    assert "DEF" in before_glosses
    assert "DEF" in after_glosses
    assert before_glosses.index("DEF") < before_glosses.index("DOG")
    assert after_glosses.index("DEF") > after_glosses.index("DOG")


def test_C3_only_active_article_morphs_are_generated():
    profile = discover_languages()["austronesian"]
    definite = Translator(profile, 52, {"articles": "definite_only"})
    indefinite = Translator(profile, 52, {"articles": "indefinite_only"})
    assert "DEF" in definite.function_morphs() and "INDEF" not in definite.function_morphs()
    assert "INDEF" in indefinite.function_morphs() and "DEF" not in indefinite.function_morphs()


def test_D1_D6_number_words_are_composed_into_contiguous_num_roots():
    profile = discover_languages()["austronesian"]
    result = Translator(profile, 53).translate("I saw twenty one birds.")[0]
    glosses = [word.gloss() for word in result.words]
    numeral = [gloss for gloss in glosses if gloss in {"TWO", "TEN", "ONE"}]
    assert numeral == ["TWO", "TEN", "ONE"]
    assert all(not word.literal for word in result.words if word.gloss() in numeral)


def test_D4_digit_scale_preserves_digits_and_realizes_scale_word():
    result = Translator(discover_languages()["austronesian"], 54).translate("I saw 3 million birds.")[0]
    assert any(word.literal and word.surface() == "3" for word in result.words)
    assert any(not word.literal and word.gloss() == "MILLION" for word in result.words)
    assert not any(word.gloss() in {"ONE", "THREE"} for word in result.words)
    digit_index = next(index for index, word in enumerate(result.words) if word.literal and word.surface() == "3")
    million_index = next(index for index, word in enumerate(result.words) if word.gloss() == "MILLION")
    assert digit_index + 1 == million_index


def test_F8_infixes_are_displayed_inside_their_host():
    from conlang.core.words import Morpheme, Word

    word = Word([Morpheme(("k", "l", "a", "t"), "JUMP", "root")])
    word.add_infix(Morpheme(("u", "m"), "AF", "infix"), 2)
    assert word.segmented() == "kl<um>at"
    assert word.gloss() == "JUMP<AF>"
    assert word.segmented().replace("-", "").replace("<", "").replace(">", "") == word.surface()


def test_E1_translate_returns_one_result_for_each_sentence():
    translator = Translator(discover_languages()["austronesian"], 61)
    results = translator.translate("Birds fly. Fish swim.")
    assert len(results) == 2
    assert [result.source_text for result in results] == ["Birds fly.", "Fish swim."]


def test_E2_np_coordination_emits_its_conjunction_once():
    translator = Translator(discover_languages()["austronesian"], 63)
    result = translator.translate("Alice and Bob left.")[0]
    assert sum(word.gloss() == "AND" for word in result.words) == 1
    assert [word.surface() for word in result.words if word.literal] == ["Alice", "Bob"]


def test_E3_embedded_and_relative_verbs_use_clause_realization():
    translator = Translator(discover_languages()["austronesian"], 65, {"pronoun_strategy": "free"})
    complement = translator.translate("I think she left.")[0]
    relative = translator.translate("The person who called left.")[0]
    assert {"THINK", "LEAVE"} <= {morpheme.gloss for word in complement.words for morpheme in word.morphemes}
    assert "Unexpected" not in " ".join(complement.rules)
    assert {"CALL"} <= {morpheme.gloss for word in relative.words for morpheme in word.morphemes}
    assert "Unexpected" not in " ".join(relative.rules)


def test_E3_clause_coordination_marker_precedes_the_linked_clause():
    translator = Translator(discover_languages()["austronesian"], 66, {"pronoun_strategy": "free"})
    result = translator.translate("Alice left and Bob ran.")[0]
    glosses = [word.gloss() for word in result.words]
    assert glosses.count("AND") == 1
    assert glosses.index("AND") < glosses.index("Bob")


def test_E4_prepositional_oblique_is_realized_once():
    result = Translator(discover_languages()["austronesian"], 67).translate("The cat is on the chair.")[0]
    assert sum(word.gloss() == "ON" for word in result.words) == 1


def test_E10_nested_adverb_is_not_absorbed_without_realization():
    translator = Translator(discover_languages()["austronesian"], 9)
    result = translator.translate("The very quick fox runs quickly.")[0]
    assert any(entry["lemma"] == "very" for entry in translator.lexicon.export())
    assert any(word.gloss() == "VERY" for word in result.words)


def test_F3_non_symmetrical_case_particles_do_not_hide_oblique_adpositions():
    translator = Translator(discover_languages()["austronesian"], 13, {
        "alignment": "active_passive", "case_particles": "preposed", "voice_affix_position": "suffix",
    })
    translator.translate("He walked into the house.")
    translator.translate("He gave a book to the child.")
    lemmas = {entry["lemma"] for entry in translator.lexicon.export()}
    assert {"into", "to"} <= lemmas


def test_E8_every_source_token_gets_a_ledger_disposition_and_residual_note():
    from conlang.core.ir import Clause, SentenceIR, SourceToken

    translator = Translator(discover_languages()["austronesian"], 69)
    sentence = SentenceIR(
        Clause(predicate="walk", predicate_pos="VERB"), "walk mystery",
        source_tokens=[SourceToken("mystery", "mystery", "NOUN", "NN", "compound")],
    )
    words, rules = translator.realizer.realize(sentence, translator.lexicon)
    assert any("residual token: mystery" == rule for rule in rules)
    assert sentence.source_tokens[0].disposition == "realized"
    assert words


def test_E8_token_ledger_covers_sentence_battery_across_twenty_seeds():
    from conlang.core.parser import parse

    sentences = (
        "Alice sees Bob.", "Bob was seen by Alice.", "The window was broken.",
        "They have eaten.", "We will go.", "We won't go.", "Did they leave?",
        "Who left?", "Open the door.", "She is happy.", "There is a problem.",
        "I gave her a book.", "Alice and Bob left.", "Alice left and Bob ran.",
        "The person who called left.", "I think she left.", "I want to swim.",
        "When the sun sets, birds sleep.", "A cup of tea is here.", "Where did you go?",
        "Three hundred and five birds flew.", "I saw 1,000 birds.", "John's red cup broke.",
        "!!!", "dogs", "the cat walked", "They have walked.",
    )
    profile = discover_languages()["austronesian"]
    for seed in range(20):
        translator = Translator(profile, seed)
        for text in sentences:
            for sentence in parse(text):
                try:
                    if sentence.clause.predicate:
                        translator.realizer.realize(sentence, translator.lexicon)
                    else:
                        translator._fallback_result(sentence.source_text, None, sentence)
                except Exception as error:
                    translator._fallback_result(sentence.source_text, error, sentence)
                assert all(token.disposition is not None for token in sentence.source_tokens), text


def test_audited_realization_passes_for_recursive_clause_and_np_paths():
    translator = Translator(discover_languages()["austronesian"], 99, {"pronoun_strategy": "free"})
    for text in ("I think she left.", "Alice left and Bob ran.", "The person who called left.", "The old woman's cup broke."):
        result = translator.translate(text, check=True)[0]
        assert "IR audit passed." in result.rules, (text, result.rules)


def test_E7_passive_by_phrase_keeps_its_adposition_before_the_agent():
    translator = Translator(discover_languages()["austronesian"], 91, {
        "alignment": "active_passive", "case_particles": "none",
    })
    result = translator.translate("Bob was seen by Alice.")[0]
    glosses = [word.gloss() for word in result.words]
    assert glosses.count("BY") == 1
    assert glosses.index("BY") < glosses.index("Alice")


def test_E5_rootless_fallback_realizes_words_instead_of_source_english():
    translator = Translator(discover_languages()["austronesian"], 93)
    result = translator.translate("Birds")[0]
    assert result.fallback_spans
    assert result.words
    assert all(not word.literal for word in result.words)
    punctuation = translator.translate("!!!")[0]
    assert punctuation.words == []
    rootless_ir = parse("Birds") [0]
    translator._fallback_result(rootless_ir.source_text, None, rootless_ir)
    assert all(token.disposition is not None for token in rootless_ir.source_tokens)


def test_E5_robustness_for_empty_punctuation_emoji_long_and_malformed_text():
    translator = Translator(discover_languages()["austronesian"], 95)
    for text in ("", "   ", "!!!", "🙂", "[[[ broken ]]]", "Birds ran. " * 300):
        result = translator.translate(text)
        assert isinstance(result, list)
        assert all(item.words is not None for item in result)


def test_F1_symmetrical_voice_marks_subject_pivot_by_relation():
    from conlang.languages.austronesian.grammar import voice_focus

    assert {role: voice_focus(role) for role in ("agent", "patient", "other")} == {
        "agent": "AF", "patient": "PF", "other": "AF",
    }
    profile = discover_languages()["austronesian"]
    translator = Translator(profile, 71, {
        "alignment": "symmetrical_voice", "case_particles": "preposed",
        "voice_affix_position": "prefix", "tam_exponence": "particle",
    })
    result = translator.translate("Alice sees Bob.")[0]
    glosses = [word.gloss() for word in result.words]
    assert glosses.count("NOM") == 1
    assert glosses.count("GEN") == 1
    assert glosses.index("NOM") < glosses.index("Alice")
    assert glosses.index("GEN") < glosses.index("Bob")


def test_F2_tam_particle_precedes_preverbal_negation_and_verb():
    translator = Translator(discover_languages()["austronesian"], 73, {
        "alignment": "plain", "case_particles": "none", "tam_exponence": "particle",
        "tam_system": "tense3", "clause_order": "SVO", "negation": "preverbal_particle",
    })
    result = translator.translate("The dog did not run.")[0]
    glosses = [word.gloss() for word in result.words]
    assert glosses.index("PAST") + 1 == glosses.index("NEG")
    assert glosses.index("NEG") + 1 == next(i for i, gloss in enumerate(glosses) if gloss.startswith("RUN"))


def test_F3_cliticized_object_has_no_orphan_case_particle():
    translator = Translator(discover_languages()["austronesian"], 75, {
        "alignment": "symmetrical_voice", "case_particles": "preposed",
        "voice_affix_position": "prefix", "pronoun_strategy": "clitic_verb",
    })
    result = translator.translate("I see him.")[0]
    glosses = [word.gloss() for word in result.words]
    assert glosses.count("NOM") == 1
    assert "GEN" not in glosses
    assert any("P3SG" in gloss for gloss in glosses)


def test_I5_personal_pronoun_map_covers_every_person_and_number_value():
    from conlang.core.ir import UNSPECIFIED
    from conlang.languages.austronesian.grammar import PERSONAL_PRONOUN_TABLE, personal_pronoun_form

    values = ("1", "2", "3", UNSPECIFIED)
    numbers = ("singular", "plural", UNSPECIFIED)
    assert set(PERSONAL_PRONOUN_TABLE) == {(person, number) for person in values for number in numbers}
    for person in values:
        for number in numbers:
            assert personal_pronoun_form(person, number, "sg_pl")
            assert personal_pronoun_form(person, number, "unmarked")


def test_I5_parser_preserves_pronoun_case_from_source_morphology():
    sentence = parse("She saw her.")[0]
    subject, object_argument = sentence.clause.arguments
    assert subject.np.case == "nom"
    assert object_argument.np.case == "acc"


def test_B4_lexicon_export_contains_used_lexical_function_and_literal_entries():
    translator = Translator(discover_languages()["austronesian"], 77)
    result = translator.translate("Mina saw the dog in 42 gardens.")[0]
    entries = translator.lexicon.export()
    assert entries == sorted(entries, key=lambda item: (item["category"], item["gloss"], item["form"]))
    assert all(set(entry) == {"form", "gloss", "lemma", "pos", "category"} for entry in entries)
    assert {entry["form"] for entry in entries if entry["category"] == "literal"} >= {"Mina", "42"}
    function_glosses = {entry["gloss"] for entry in entries if entry["category"] == "function"}
    for word in result.words:
        for morpheme in word.morphemes:
            if morpheme.gloss in translator.function_morphs():
                assert morpheme.gloss in function_glosses


def test_B2_every_post_epenthesis_output_morpheme_appears_in_lexicon_export():
    translator = Translator(discover_languages()["austronesian"], 14)
    results = [translator.translate(text)[0] for text in (
        "The child saw two birds.", "Will you come home?", "The door was opened by Mina.",
        "I gave her a book.", "She is not at home.", "These dogs run.", "The cat and the dog ran.",
    )]
    exported = {entry["form"] for entry in translator.lexicon.export()}
    missing = [
        (morpheme.gloss, "".join(morpheme.segments))
        for result in results for word in result.words if not word.literal
        for morpheme in word.morphemes if morpheme.kind != "epenthetic"
        and "".join(morpheme.segments) not in exported
    ]
    assert not missing, missing[:5]


def test_F4_two_way_demonstrative_pronoun_is_the_particle():
    translator = Translator(discover_languages()["austronesian"], 79, {"demonstratives": "two_way"})
    result = translator.translate("These are tall.")[0]
    glosses = [word.gloss() for word in result.words]
    assert "PROX" in glosses
    assert "THESE" not in glosses


def test_F4_unmarked_determiners_keep_their_ordinary_lexical_form():
    translator = Translator(discover_languages()["austronesian"], 80, {"demonstratives": "unmarked"})
    result = translator.translate("This dog is friendly.")[0]
    assert any(word.gloss() == "THIS" for word in result.words)


def test_F5_possessor_noun_phrase_preserves_literal_name_and_position():
    translator = Translator(discover_languages()["austronesian"], 81, {"possessor_position": "before"})
    result = translator.translate("John's red cup broke.")[0]
    glosses = [word.gloss() for word in result.words]
    assert "John" in glosses
    assert glosses.index("John") < glosses.index("CUP")
    assert "RED" in glosses


def test_F6_F7_lexical_roots_use_the_parser_pos():
    profile = discover_languages()["austronesian"]
    translator = Translator(profile, 83)
    translator.translate("The dog is very quick.")
    translator.translate("The chicken soup cooled.")
    assert ("quick", "ADJ") in translator.lexicon.entries
    assert ("chicken", "NOUN") in translator.lexicon.entries


def test_F9_plain_alignment_rejects_vacuous_case_particles():
    from conlang.core.features import IncompatibleFeatures

    try:
        discover_languages()["austronesian"].catalog.sample(85, {
            "alignment": "plain", "case_particles": "preposed",
        })
    except IncompatibleFeatures as error:
        assert "plain_has_no_case_particles" in error.constraint_ids
    else:
        raise AssertionError("plain alignment accepted vacuous case particles")


def test_F10_modifier_submodifiers_stay_adjacent_in_english_order():
    result = Translator(discover_languages()["austronesian"], 87).translate("The very quick dog ran.")[0]
    glosses = [word.gloss() for word in result.words]
    assert glosses.index("VERY") + 1 == glosses.index("QUICK")


def test_F11_proper_names_and_digits_are_literal_and_exempt_from_phonotactics():
    result = Translator(discover_languages()["austronesian"], 89).translate("Mina saw 42 birds.")[0]
    literals = [word for word in result.words if word.literal]
    assert [word.surface() for word in literals] == ["Mina", "42"]
