"""Pinned spaCy model management and source-text preservation."""

import importlib.metadata
from functools import lru_cache


class EnglishParser:
    MODEL_NAME = "en_core_web_sm"
    MODEL_VERSION = "3.8.0"

    @staticmethod
    @lru_cache(maxsize=1)
    def model():
        try:
            import spacy

            nlp = spacy.load(EnglishParser.MODEL_NAME)
        except Exception as error:
            raise RuntimeError(
                "English parser unavailable. Install with: "
                "python -m spacy download en_core_web_sm-3.8.0"
            ) from error
        if nlp.meta.get("version") != EnglishParser.MODEL_VERSION:
            raise RuntimeError(
                f"Expected {EnglishParser.MODEL_NAME} {EnglishParser.MODEL_VERSION}, "
                f"found {nlp.meta.get('version')}. Install with: "
                "python -m spacy download en_core_web_sm-3.8.0"
            )
        return nlp

    @staticmethod
    def is_all_caps(text):
        letters = [char for char in text if char.isalpha()]
        return len(letters) >= 2 and all(char.isupper() for char in letters)

    @classmethod
    def analyze(cls, text):
        """Parse a lowercased copy of all-caps text; preserve the original text."""
        parse_text = (
            text.lower() if cls.is_all_caps(text) and len(text.lower()) == len(text) else text
        )
        doc = cls.model()(parse_text)
        doc.user_data["original"] = text
        return doc

    @staticmethod
    def original(token):
        original = token.doc.user_data.get("original")
        if original is None:
            return token.text
        return original[token.idx : token.idx + len(token.text)]

    @staticmethod
    def span_text(span):
        original = span.doc.user_data.get("original")
        return span.text if original is None else original[span.start_char : span.end_char]

    @staticmethod
    def morphology(token):
        return {key: tuple(value.split(",")) for key, value in token.morph.to_dict().items()}

    @staticmethod
    def versions():
        try:
            spacy_version = importlib.metadata.version("spacy")
        except importlib.metadata.PackageNotFoundError:
            spacy_version = "missing"
        try:
            model_version = importlib.metadata.version("en-core-web-sm")
        except importlib.metadata.PackageNotFoundError:
            model_version = "missing"
        return {"spacy": spacy_version, "model": model_version}
