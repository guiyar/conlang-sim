"""Registered V1 Austronesian-inspired language profile."""

from conlang.core.registry import register_language
from .catalog import CATALOG
from .grammar import Realizer
from .phonology import Phonology


@register_language
class Austronesian:
    language_id = "austronesian"
    name = "Austronesian"
    description = "A seeded conlang profile drawing on selected Austronesian patterns."
    output_version = 1
    catalog = CATALOG
    phonology_class = Phonology
    realizer_class = Realizer

    @staticmethod
    def phonology(features, seed, language_id, output_version):
        return Phonology(features, seed, language_id, output_version)

    @staticmethod
    def realize(ir, translator):
        return translator.realizer.realize(ir, translator.lexicon)

    @staticmethod
    def describe(features, parameters):
        return f"Austronesian dialect v1\nFeatures: {features}\nForm parameters: {parameters}"