"""Deterministic UTF-8 JSON used by workspace authority records."""
from __future__ import annotations

import json


def canonical_json(value: object, *, sort_keys: bool = True) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=sort_keys, allow_nan=False) + '\n'


def read_json(payload: bytes):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError(f'Nonfinite JSON number: {value}')
    return json.loads(payload.decode('utf-8'), object_pairs_hook=object_pairs,
                      parse_constant=reject_constant)
