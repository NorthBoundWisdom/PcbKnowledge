"""Offline structural validator for the workspace JSON Schema subset."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re

SCHEMA_DIR = Path(__file__).resolve().parents[3] / 'schemas'
KEYWORDS = frozenset({'$schema', '$id', '$ref', '$defs', 'title', 'description',
    'type', 'const', 'enum', 'properties', 'required', 'additionalProperties',
    'propertyNames', 'items', 'minItems', 'maxItems', 'uniqueItems', 'minProperties', 'maxProperties',
    'minLength', 'maxLength', 'pattern', 'minimum', 'maximum', 'exclusiveMinimum',
    'oneOf', 'anyOf', 'allOf', 'not'})


def _number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _equal(left, right):
    if _number(left) and _number(right):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


class ContractSchemas:
    def __init__(self, directory=SCHEMA_DIR):
        self.directory = Path(directory)
        self.documents = {}

    def load(self, name):
        if not isinstance(name, str) or re.fullmatch(r'[a-z0-9-]+\.schema\.json', name) is None:
            raise ValueError('Schema reference must name a sibling schema file')
        if name not in self.documents:
            path = self.directory / name
            if path.is_symlink():
                raise ValueError('Schema symlinks are forbidden')
            self.documents[name] = json.loads(path.read_text(encoding='utf-8'))
        return self.documents[name]

    def resolve(self, reference, current):
        if not isinstance(reference, str) or reference.count('#') > 1:
            raise ValueError('Malformed schema reference')
        filename, _, pointer = reference.partition('#')
        filename = filename or current
        target = self.load(filename)
        if pointer:
            if not pointer.startswith('/'):
                raise ValueError('Only JSON pointer fragments are supported')
            for token in pointer[1:].split('/'):
                target = target[token.replace('~1', '/').replace('~0', '~')]
        return target, filename

    def check(self, schema, current, visited=None):
        if isinstance(schema, bool):
            return
        if not isinstance(schema, dict) or set(schema) - KEYWORDS:
            raise ValueError('Unsupported schema keyword or malformed schema')
        visited = set() if visited is None else visited
        if '$ref' in schema:
            key = (current, schema['$ref'])
            if key not in visited:
                visited.add(key)
                target, filename = self.resolve(schema['$ref'], current)
                self.check(target, filename, visited)
        for key in ('$defs', 'properties'):
            for child in schema.get(key, {}).values():
                self.check(child, current, visited)
        for key in ('items', 'additionalProperties', 'not', 'propertyNames'):
            if key in schema:
                self.check(schema[key], current, visited)
        for key in ('oneOf', 'anyOf', 'allOf'):
            for child in schema.get(key, []):
                self.check(child, current, visited)

    def apply(self, value, schema, current, depth=0):
        if depth > 80:
            raise ValueError('Contract nesting exceeds schema evaluator bound')
        if schema is True:
            return
        if schema is False:
            raise ValueError('False schema')
        def child(v, s, name=current):
            return self.apply(v, s, name, depth+1)
        if '$ref' in schema:
            target, name = self.resolve(schema['$ref'], current)
            child(value, target, name)
        types = {'object': lambda v: isinstance(v, dict), 'array': lambda v: isinstance(v, list),
                 'string': lambda v: isinstance(v, str), 'boolean': lambda v: type(v) is bool,
                 'integer': lambda v: _number(v) and int(v) == v,
                 'number': lambda v: _number(v),
                 'null': lambda v: v is None}
        if 'type' in schema and not types[schema['type']](value):
            raise ValueError('Type mismatch')
        if 'const' in schema and not _equal(value, schema['const']):
            raise ValueError('Constant mismatch')
        if 'enum' in schema and not any(_equal(value, v) for v in schema['enum']):
            raise ValueError('Unknown enumeration value')
        if isinstance(value, dict):
            if any(key not in value for key in schema.get('required', [])):
                raise ValueError('Missing required property')
            for key, v in value.items():
                if 'propertyNames' in schema:
                    child(key, schema['propertyNames'])
                child(v, schema.get('properties', {}).get(key, schema.get('additionalProperties', True)))
            for keyword, comparison in [('minProperties', lambda a,b:a<b),('maxProperties',lambda a,b:a>b)]:
                if keyword in schema and comparison(len(value),schema[keyword]):
                    raise ValueError('Object size mismatch')
        if isinstance(value, list):
            for v in value:
                child(v, schema.get('items', True))
            if len(value)<schema.get('minItems',0) or len(value)>schema.get('maxItems',math.inf):
                raise ValueError('Array size mismatch')
            if schema.get('uniqueItems') and any(_equal(v, prior) for i, v in enumerate(value) for prior in value[:i]):
                raise ValueError('Duplicate item')
        if isinstance(value, str):
            if len(value)<schema.get('minLength',0) or len(value)>schema.get('maxLength',math.inf):
                raise ValueError('String size mismatch')
            if 'pattern' in schema and re.search(schema['pattern'],value) is None:
                raise ValueError('Pattern mismatch')
        if type(value) in (int,float):
            if not _number(value):
                raise ValueError('Nonfinite number')
            if value<schema.get('minimum',-math.inf) or value>schema.get('maximum',math.inf):
                raise ValueError('Numeric range mismatch')
            if 'exclusiveMinimum' in schema and value<=schema['exclusiveMinimum']:
                raise ValueError('Exclusive minimum mismatch')
        for key in ('oneOf','anyOf','allOf'):
            if key in schema:
                passes=0
                for branch in schema[key]:
                    try: child(value,branch)
                    except ValueError: pass
                    else: passes+=1
                if ((key=='oneOf' and passes!=1) or (key=='anyOf' and passes==0)
                        or (key=='allOf' and passes!=len(schema[key]))):
                    raise ValueError(key+' mismatch')
        if 'not' in schema:
            try: child(value,schema['not'])
            except ValueError: pass
            else: raise ValueError('Forbidden shape')


def validate(instance, schema_name, schema_dir=None):
    schemas = ContractSchemas(SCHEMA_DIR if schema_dir is None else schema_dir)
    schema = schemas.load(schema_name)
    schemas.check(schema, schema_name)
    schemas.apply(instance, schema, schema_name)
