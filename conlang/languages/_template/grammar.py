"""Realization stub for a new profile."""


class TemplateRealizer:
    def __init__(self, features, phonology, seed, language_id, output_version):
        self.features = dict(features)
        self.phonology = phonology
        self.seed = seed
        self.language_id = language_id
        self.output_version = output_version

    def function_forms(self):
        return set()

    def function_morphs(self):
        return {}

    def realize(self, ir, lexicon):
        return [], []
