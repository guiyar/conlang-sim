"""Form-only phonology stub for a new profile."""


class TemplatePhonology:
    def __init__(self, features, seed, language_id="template", output_version=1):
        self.features = dict(features)
        self.seed = seed
        self.language_id = language_id
        self.output_version = output_version
        self.parameters = {}