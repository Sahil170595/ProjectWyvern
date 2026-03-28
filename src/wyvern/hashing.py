from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel


def canonical_json(obj: BaseModel) -> bytes:
    """Deterministic JSON: sorted keys, no extra whitespace.

    Uses model_dump(mode='json') for Pydantic 2.x compatible serialization
    (datetimes become ISO strings, enums become values).
    """
    data = obj.model_dump(mode="json")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sha256_hash(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def hash_model(obj: BaseModel) -> str:
    return sha256_hash(canonical_json(obj))
