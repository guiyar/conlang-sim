"""Non-discovered profile skeleton; register after assigning a real language ID."""

from .catalog import CATALOG, OUTPUT_VERSION
from .grammar import TemplateRealizer
from .phonology import TemplatePhonology


class TemplateProfile:
    language_id = "template"
    name = "Template"
    description = "Starting point for a new language-family profile."
    output_version = OUTPUT_VERSION
    catalog = CATALOG
    phonology_class = TemplatePhonology
    realizer_class = TemplateRealizer

    @staticmethod
    def phonology(features, seed, language_id, output_version):
        return TemplatePhonology(features, seed, language_id, output_version)

    @staticmethod
    def realize(ir, translator):
        return translator.realizer.realize(ir, translator.lexicon)

    @staticmethod
    def describe(features, parameters, **kwargs):
        return (
            f"Template dialect v{OUTPUT_VERSION}; choose a language ID and implement realization."
        )
