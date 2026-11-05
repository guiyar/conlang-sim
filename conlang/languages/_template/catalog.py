"""Minimal feature catalog for a new language profile."""

from conlang.core.features import Feature, FeatureCatalog, Option

OUTPUT_VERSION = 1
FEATURES = (
    Feature(
        "vowel_inventory", "phonology", (Option("basic"), Option("expanded")),
        meaning_bearing=False,
    ),
)
CATALOG = FeatureCatalog(FEATURES, language_id="template", output_version=OUTPUT_VERSION)