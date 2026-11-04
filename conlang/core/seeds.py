"""Stable seed derivation and independent random streams."""

import hashlib
import json
import random


def derive_seed(master, *parts):
    payload = json.dumps([str(master), *map(str, parts)], ensure_ascii=True, separators=(",", ":"))
    return int.from_bytes(hashlib.sha256(payload.encode("utf-8")).digest(), "big")


def item_rng(master, language_id, output_version, subsystem, item_key):
    return random.Random(derive_seed(master, language_id, output_version, subsystem, item_key))