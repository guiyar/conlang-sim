"""Austronesian profile feature inventory and logical constraints."""

from conlang.core.features import Constraint, Feature, FeatureCatalog, Option

EXCLUDED_FEATURES = (
    ("clusivity", 'English "we" does not distinguish inclusive and exclusive'),
    ("dual_trial_number", "English plural does not determine exact count"),
    ("possessive_classes", "Alienability is not marked in English"),
    ("three_way_demonstratives", "English has a two-way distinction"),
    ("locative_instrument_focus", "English voice does not determine pivot selection"),
    ("honorifics_politeness", "Not reliably derivable from English"),
    ("evidentiality", "Source of information is not encoded"),
    ("animacy_noun_classes", "Not reliably derivable from English"),
)


def opt(name, attested=(), status=None):
    return Option(name, attested_in=tuple(attested), status=status or ("attested" if attested else "invented"))


def feature(fid, group, options, fields=(), applies=None):
    return Feature(fid, group, tuple(options), applies, bool(fields), tuple(fields))


FEATURES = (
    feature("vowels", "phonology", [opt("v3"), opt("v5")]),
    feature("vowel_length", "phonology", [opt("none"), opt("contrastive", ("Maori", "Hawaiian", "Samoan"))]),
    feature("stop_voicing", "phonology", [opt("voiceless_only"), opt("voiced_and_voiceless")]),
    feature("prenasalized_stops", "phonology", [opt("no"), opt("yes", ("Fijian", "Malagasy"))]),
    feature("glottal_stop", "phonology", [opt("no"), opt("yes", ("Tagalog", "Hawaiian", "Samoan"))]),
    feature("fricatives", "phonology", [opt("h"), opt("h_s"), opt("h_s_f_v")]),
    feature("nasals", "phonology", [opt("m_n"), opt("m_n_ng"), opt("m_n_ng_ny")]),
    feature("liquids", "phonology", [opt("l"), opt("r"), opt("l_r")]),
    feature("syllable_structure", "phonology", [opt("open"), opt("closed"), opt("closed_clusters")]),
    feature("word_initial_vowel", "phonology", [opt("no"), opt("yes")]),
    feature("alignment", "morphosyntax", [opt("symmetrical_voice", ("Tagalog", "Cebuano")), opt("active_passive", ("Malay", "Indonesian")), opt("ergative", ("Samoan", "Tongan", "Maori")), opt("plain")], ("clause.voice", "clause.transitivity", "argument.role")),
    feature("voice_affix_position", "morphosyntax", [opt("prefix"), opt("infix"), opt("suffix")], ("clause.voice",), {"alignment": ("symmetrical_voice", "active_passive")}),
    feature("case_particles", "morphosyntax", [opt("none"), opt("preposed")], ("argument.role", "argument.relation")),
    feature("clause_order", "morphosyntax", [opt("VSO"), opt("VOS"), opt("SVO"), opt("SOV")], ("argument.relation", "clause.kind")),
    feature("tam_system", "morphosyntax", [opt("tense3"), opt("past_nonpast"), opt("aspect3")], ("clause.tense", "clause.perfect", "clause.progressive")),
    feature("tam_exponence", "morphosyntax", [opt("particle"), opt("affix")], ("clause.tense", "clause.perfect", "clause.progressive")),
    feature("tam_affix_position", "morphosyntax", [opt("prefix"), opt("suffix")], ("clause.tense", "clause.perfect", "clause.progressive"), {"tam_exponence": "affix"}),
    feature("imperfective_reduplication", "morphosyntax", [opt("no"), opt("yes", ("Tagalog",))], ("clause.tense", "clause.perfect", "clause.progressive"), {"tam_system": "aspect3"}),
    feature("noun_number", "morphosyntax", [opt("none"), opt("particle"), opt("full_reduplication"), opt("partial_reduplication", ("Malay", "Indonesian", "Tagalog"))], ("np.number",)),
    feature("pronoun_strategy", "morphosyntax", [opt("free"), opt("clitic_second"), opt("clitic_verb", ("Tagalog",))], ("np.head.kind", "argument.relation")),
    feature("pronoun_number", "morphosyntax", [opt("sg_pl"), opt("unmarked")], ("np.pronoun.person", "np.pronoun.number")),
    feature("modifier_position", "morphosyntax", [opt("after"), opt("before")], ("np.modifiers",)),
    feature("linker", "morphosyntax", [opt("none"), opt("particle", ("Tagalog",))], ("np.modifiers",), {"modifier_position": "after"}),
    feature("possessor_position", "morphosyntax", [opt("before"), opt("after")], ("np.possessor",)),
    feature("demonstratives", "morphosyntax", [opt("unmarked"), opt("two_way")], ("np.demonstrative", "np.head.kind")),
    feature("question", "morphosyntax", [opt("particle_initial"), opt("particle_final"), opt("none")], ("clause.mood",)),
    feature("negation", "morphosyntax", [opt("preverbal_particle"), opt("clause_initial_particle")], ("clause.polarity",)),
)

CONSTRAINTS = (
    Constraint("prenasal_requires_voiced_stops", {"prenasalized_stops": "yes"}, {"stop_voicing": "voiced_and_voiceless"}, "dependency", "Prenasalized stop series are built from voiced stop places in this inventory."),
    Constraint("infix_requires_coda", {"voice_affix_position": "infix"}, {"syllable_structure": ("closed", "closed_clusters")}, "licensing", "The VC infix needs a licensed post-onset position; either closed structure supplies it."),
    Constraint("infix_requires_consonant_initial", {"voice_affix_position": "infix"}, {"word_initial_vowel": "no"}, "licensing", "Every root must have an onset site for the infix."),
    Constraint("alignment_requires_case", {"alignment": ("symmetrical_voice", "ergative")}, {"case_particles": "preposed"}, "dependency", "Symmetrical voice and ergative systems in this profile require overt role marking."),
)

CATALOG = FeatureCatalog(FEATURES, CONSTRAINTS, EXCLUDED_FEATURES, "austronesian", 1)