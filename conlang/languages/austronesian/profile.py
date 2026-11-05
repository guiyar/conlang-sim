"""Registered V1 Austronesian-inspired language profile."""

from conlang.core.registry import register_language
from .catalog import CATALOG, OUTPUT_VERSION
from .grammar import Realizer
from .phonology import Phonology

CLOSED_CLASS = (
    ("some", "DET"), ("any", "DET"), ("no", "DET"), ("every", "DET"),
    ("each", "DET"), ("all", "DET"), ("both", "DET"), ("another", "DET"),
    ("other", "DET"), ("such", "DET"), ("either", "DET"), ("neither", "DET"),
    ("much", "DET"), ("many", "DET"), ("few", "DET"), ("several", "DET"),
    ("enough", "DET"), ("half", "DET"),
    ("of", "ADP"), ("in", "ADP"), ("on", "ADP"), ("at", "ADP"), ("to", "ADP"),
    ("from", "ADP"), ("with", "ADP"), ("without", "ADP"), ("by", "ADP"),
    ("for", "ADP"), ("into", "ADP"), ("onto", "ADP"), ("over", "ADP"),
    ("under", "ADP"), ("about", "ADP"), ("above", "ADP"), ("below", "ADP"),
    ("between", "ADP"), ("through", "ADP"), ("during", "ADP"), ("before", "ADP"),
    ("after", "ADP"), ("near", "ADP"), ("across", "ADP"), ("behind", "ADP"),
    ("beside", "ADP"), ("toward", "ADP"), ("against", "ADP"), ("along", "ADP"),
    ("around", "ADP"), ("among", "ADP"), ("upon", "ADP"), ("off", "ADP"),
    ("and", "CCONJ"), ("or", "CCONJ"), ("but", "CCONJ"), ("nor", "CCONJ"),
    ("so", "CCONJ"), ("yet", "CCONJ"),
    ("because", "SCONJ"), ("if", "SCONJ"), ("that", "SCONJ"), ("when", "SCONJ"),
    ("while", "SCONJ"), ("although", "SCONJ"), ("though", "SCONJ"), ("since", "SCONJ"),
    ("until", "SCONJ"), ("unless", "SCONJ"), ("whether", "SCONJ"), ("as", "SCONJ"),
    ("than", "SCONJ"), ("once", "SCONJ"), ("to", "PART"),
    ("be", "AUX"), ("have", "AUX"), ("do", "AUX"), ("will", "AUX"),
    ("would", "AUX"), ("can", "AUX"), ("could", "AUX"), ("may", "AUX"),
    ("might", "AUX"), ("shall", "AUX"), ("should", "AUX"), ("must", "AUX"),
    ("who", "PRON"), ("whom", "PRON"), ("whose", "PRON"), ("which", "PRON"),
    ("what", "PRON"), ("someone", "PRON"), ("something", "PRON"), ("anyone", "PRON"),
    ("anything", "PRON"), ("everyone", "PRON"), ("everything", "PRON"),
    ("nobody", "PRON"), ("nothing", "PRON"), ("one", "PRON"), ("itself", "PRON"),
    ("himself", "PRON"), ("herself", "PRON"), ("themselves", "PRON"),
    ("myself", "PRON"), ("yourself", "PRON"), ("ourselves", "PRON"),
    ("very", "ADV"), ("too", "ADV"), ("also", "ADV"), ("only", "ADV"),
    ("just", "ADV"), ("here", "ADV"), ("there", "ADV"), ("now", "ADV"),
    ("then", "ADV"), ("again", "ADV"), ("always", "ADV"), ("never", "ADV"),
    ("often", "ADV"), ("still", "ADV"), ("already", "ADV"), ("even", "ADV"),
    ("more", "ADV"), ("most", "ADV"), ("less", "ADV"), ("quite", "ADV"),
    ("how", "ADV"), ("where", "ADV"), ("why", "ADV"), ("soon", "ADV"),
    ("perhaps", "ADV"), ("yes", "INTJ"), ("no", "INTJ"), ("hello", "INTJ"),
    ("please", "INTJ"),
)

_EARLY_CLOSED_CLASS = (
    ("in", "ADP"), ("of", "ADP"), ("on", "ADP"), ("at", "ADP"), ("to", "ADP"),
    ("and", "CCONJ"), ("because", "SCONJ"),
    ("near", "ADP"),
    ("this", "DET"), ("that", "DET"), ("these", "DET"), ("those", "DET"),
    ("who", "PRON"), ("which", "DET"), ("what", "DET"), ("whose", "DET"),
    ("here", "ADV"), ("where", "ADV"), ("when", "ADV"), ("why", "ADV"),
    ("very", "ADV"), ("now", "ADV"), ("there", "ADV"),
)
CLOSED_CLASS = _EARLY_CLOSED_CLASS + tuple(item for item in CLOSED_CLASS if item not in _EARLY_CLOSED_CLASS)


def word_shape(pos):
    if pos == "NUM":
        return "numeral"
    if pos in {"DET", "ADP", "CCONJ", "SCONJ", "PART", "AUX", "PRON", "INTJ"}:
        return "function"
    return "content"


@register_language
class Austronesian:
    language_id = "austronesian"
    name = "Austronesian"
    description = "A seeded conlang profile drawing on selected Austronesian patterns."
    output_version = OUTPUT_VERSION
    catalog = CATALOG
    phonology_class = Phonology
    realizer_class = Realizer
    CLOSED_CLASS = CLOSED_CLASS
    closed_class = CLOSED_CLASS
    word_shape = staticmethod(word_shape)

    @staticmethod
    def phonology(features, seed, language_id, output_version):
        return Phonology(features, seed, language_id, output_version)

    @staticmethod
    def realize(ir, translator):
        return translator.realizer.realize(ir, translator.lexicon)

    @staticmethod
    def describe(features, parameters, phonology=None, function_morphs=None):
        vowels = ", ".join(phonology.vowels) if phonology else "unavailable"
        consonants = ", ".join(phonology.consonants) if phonology else "unavailable"
        codas = ", ".join(phonology.codas) if phonology else "unavailable"
        structure = features["syllable_structure"]
        template = "CV, with optional V word-initially" if structure == "open" else "CV/CVC"
        if structure == "closed_clusters":
            template += ", with rare stop-liquid onset clusters"
        lines = [
            f"Austronesian dialect v{OUTPUT_VERSION}",
            f"Vowels: {vowels}",
            f"Consonants: {consonants}",
            f"Syllable template: {template}; coda probability={parameters['coda_probability']:.3f}; cluster probability={parameters['cluster_probability']:.3f}",
            f"Codas: {codas}",
            f"Word order: {features['clause_order']}",
            f"Alignment: {features['alignment']}",
            f"Article system: {features['articles']} ({features['article_position'] or 'not applicable'})",
            f"TAM system: {features['tam_system']} ({features['tam_exponence']})",
            "Function morphs:",
        ]
        if function_morphs:
            lines.extend(f"  {gloss} -> {form}" for gloss, form in sorted(function_morphs.items()))
        return "\n".join(lines)