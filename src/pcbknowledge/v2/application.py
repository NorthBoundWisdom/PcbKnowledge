"""Construct read-only catalog view models from the selected workspace."""
from __future__ import annotations

from pathlib import Path
from .catalog import Catalog, ELIGIBLE


def _row(label, value, evidence=None):
    return {'label': label, 'value': value, 'evidence': evidence}


def _part_rows(record):
    rows = [
        _row('Identity', record['manufacturer'] + ' / ' + record['mpn'], record['identity_evidence']),
        _row('Package', record['package'], record['identity_evidence']),
    ]
    for pin in record['pins']:
        rows.append(_row('Pin ' + pin['number'], pin['name'] + ' / ' + pin['type'], record['pin_evidence']))
    for name, value in record['parameters'].items():
        rows.append(_row(name, value, value.get('evidence')))
    return rows


def _value_rows(label, value):
    if isinstance(value, dict):
        if 'basis' in value or value.get('status') == 'UNKNOWN':
            return [_row(label, value, value.get('evidence'))]
        if not value:
            return [_row(label, value)]
        rows = []
        for name, child in value.items():
            rows.extend(_value_rows(label + '/' + name, child))
        return rows
    if isinstance(value, list) and value:
        rows = []
        for index, child in enumerate(value):
            rows.extend(_value_rows(label + '/' + str(index), child))
        return rows
    return [_row(label, value)]


def _block_rows(record):
    rows = []
    for index, anchor in enumerate(record['evidence']):
        rows.append(_row('Block reference ' + str(index + 1), anchor['source'], anchor))
    for name in ('parameters', 'ports', 'components', 'nets', 'checks', 'layout'):
        rows.extend(_value_rows(name, record[name]))
    return rows


def _citation(catalog, evidence):
    if not evidence or 'source' not in evidence:
        return None
    source = catalog.get(evidence['source'], 'source')
    if source['license_class'] not in ELIGIBLE:
        return {'blocked': True}
    return {
        'source': source['id'], 'page': evidence['page'],
        'media_type': source.get('media_type', 'application/pdf'),
        'url': source['url'], 'sha256': source['sha256'], 'accessed_on': source['accessed_on'],
    }


class Application:
    def __init__(self, root: Path):
        self.root = root

    def index(self):
        catalog = Catalog(self.root, self.root / 'schemas')
        return {
            'title': 'PcbKnowledge', 'workspace': str(self.root),
            'parts': catalog.search('part'), 'blocks': catalog.search('block'),
        }

    def record(self, identity, kind):
        catalog = Catalog(self.root, self.root / 'schemas')
        if identity not in catalog.records:
            raise LookupError('Record not found')
        record = catalog.get(identity, kind)
        rows = _part_rows(record) if kind == 'part' else _block_rows(record)
        for row in rows:
            row['citation'] = _citation(catalog, row['evidence'])
        return {
            'title': record.get('mpn', record['id']), 'workspace': str(self.root),
            'record': record, 'rows': rows,
        }

    def evidence(self, identity):
        catalog = Catalog(self.root, self.root / 'schemas')
        path = catalog.authorize_read(identity)
        if catalog.get(identity, 'source').get('media_type', 'application/pdf') != 'application/pdf':
            raise ValueError('HTML evidence is external-link only; active source HTML is never served here.')
        return path.read_bytes()
