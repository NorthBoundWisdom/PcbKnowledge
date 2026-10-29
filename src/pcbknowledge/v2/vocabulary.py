"""Registry membership, canonical quantities and parameter condition validation."""
from __future__ import annotations

from pcbknowledge.serialization import read_json
from pathlib import Path

from .schema import validate


class Vocabulary:
    def __init__(self, documents):
        self.entries = {d['id'].removeprefix('registry:'): d['entries'] for d in documents}
        expected = {'quantities', 'parameters', 'roles', 'pin-types', 'package-families', 'layout-constraints'}
        if set(self.entries) != expected or len(documents) != len(expected):
            raise ValueError('Incomplete or duplicate registry set')
        quantities = self.entries['quantities']
        for name, definition in self.entries['parameters'].items():
            self.member('quantities', definition['quantity'])
            for quantity in definition['conditions'].values():
                self.member('quantities', quantity)
        units = [entry['unit'] for entry in quantities.values()]
        if len(units) != len(set(units)):
            raise ValueError('Canonical units must identify one quantity')

    @classmethod
    def load(cls, directory: Path, schema_dir: Path):
        documents = []
        for path in (directory, directory.parent):
            if path.is_symlink():raise ValueError('Registry directory symlinks are forbidden')
        for path in sorted(directory.glob('*.json')):
            if path.is_symlink():
                raise ValueError('Registry symlinks are forbidden')
            if path.stat().st_size > 1_000_000:raise ValueError('Oversized registry')
            document = read_json(path.read_bytes())
            validate(document, 'registry.schema.json', schema_dir)
            if path.stem != document['id'].removeprefix('registry:'):
                raise ValueError('Registry filename does not match its identity')
            documents.append(document)
        return cls(documents)

    def member(self, registry, name):
        if name not in self.entries[registry]:
            raise ValueError(f'Unknown {registry} name: {name}')
        return self.entries[registry][name]

    def quantity(self, value, quantity=None, conditions=None):
        if value.get('status') == 'UNKNOWN':
            return
        allowed_units = {v['unit'] for v in self.entries['quantities'].values()}
        if value['unit'] not in allowed_units:
            raise ValueError(f'Unknown canonical unit: {value["unit"]}')
        if quantity and value['unit'] != self.member('quantities', quantity)['unit']:
            raise ValueError(f'Wrong canonical unit for {quantity}: {value["unit"]}')
        numbers = [value[k] for k in ('min', 'typ', 'max') if k in value]
        if numbers != sorted(numbers):
            raise ValueError('Quantity requires min <= typ <= max')
        if conditions is None:
            conditions = {}
            for entry in self.entries['parameters'].values():
                for key, kind in entry['conditions'].items():
                    if key in conditions and conditions[key] != kind:
                        raise ValueError(f'Conflicting condition quantity: {key}')
                    conditions[key] = kind
        for key, condition in value.get('conditions', {}).items():
            if key not in conditions:
                raise ValueError(f'Condition not allowed: {key}')
            self.quantity(condition, conditions[key], {})

    def parameters(self, parameters, declarations=False):
        for name, value in parameters.items():
            entry = self.member('parameters', name)
            if declarations:
                if value['quantity'] != entry['quantity']:
                    raise ValueError(f'Wrong declared quantity for {name}')
            else:
                self.quantity(value, entry['quantity'], entry['conditions'])

    def document(self, document):
        """Validate vocabulary and value semantics without resolving catalog references."""
        def walk(value, key=None):
            if isinstance(value, list):
                for child in value:
                    walk(child, key)
                return
            if not isinstance(value, dict):
                return
            if 'unit' in value:
                quantity = self.entries['parameters'].get(key, {}).get('quantity')
                field_quantities = {
                    'voltage':'voltage', 'current_budget':'current', 'current_limit':'current',
                    'max_length':'length', 'max_width':'length', 'height_limit':'length',
                    'x':'length', 'y':'length', 'rotation':'angle', 'angle':'angle',
                    'courtyard_margin':'length', 'keepout_diameter':'length', 'edge_offset':'length',
                    'distance':'length', 'max_distance':'length', 'max_area':'area', 'min_area':'area',
                    'min_width':'length', 'min_clearance':'length', 'margin':'length',
                    'trace_width_min':'length', 'clearance_min':'length', 'drill_min':'length',
                    'annular_ring_min':'length', 'solder_mask_web_min':'length'}
                self.quantity(value, field_quantities.get(key, quantity))
            if 'parameters' in value:
                self.parameters(value['parameters'], document.get('schema') == 'pcbknowledge.block.v2')
            for name, registry in (('roles', 'roles'), ('family', 'package-families')):
                if name in value:
                    for item in value[name] if isinstance(value[name], list) else [value[name]]:
                        self.member(registry, item)
            if key == 'ports' and 'kind' in value:
                self.member('pin-types', value['kind'])
            if 'pin_type' in value:
                self.member('pin-types', value['pin_type'])
            if 'role' in value:
                self.member('roles', value['role'])
            if key in ('pins', 'ports') and 'type' in value:
                self.member('pin-types', value['type'])
            if 'parameter' in value:
                self.member('parameters', value['parameter'])
            if 'match' in value:
                self.parameters(value['match'])
            if key == 'layout':
                entry = self.member('layout-constraints', value['kind'])
                if set(value) != {'kind', *entry['fields']}:
                    raise ValueError(f'Wrong fields for layout kind {value["kind"]}')
            for name, child in value.items():
                walk(child, name)
        if document.get('schema') == 'pcbknowledge.registry.v2':
            return
        walk(document)
