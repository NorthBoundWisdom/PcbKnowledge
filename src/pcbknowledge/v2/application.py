"""Construct read-only catalog view models from the selected workspace."""
from __future__ import annotations

from pathlib import Path
from .catalog import Catalog


class Application:
    def __init__(self, root: Path):
        self.root = root

    def index(self):
        catalog = Catalog(self.root, self.root/'schemas')
        return {'title':'PcbKnowledge','workspace':str(self.root), 'parts':catalog.search('part'), 'blocks':catalog.search('block')}

    def record(self, identity, kind):
        catalog = Catalog(self.root, self.root/'schemas')
        if identity not in catalog.records:
            raise LookupError('Record not found')
        record = catalog.get(identity, kind)
        rows = []
        def append(label, value, evidence=None):
            rows.append({'label':label, 'value':value, 'evidence':evidence})
        if kind == 'part':
            append('Identity', record['manufacturer']+' / '+record['mpn'], record['identity_evidence'])
            append('Package', record['package'], record['identity_evidence'])
            for pin in record['pins']:
                append('Pin '+pin['number'], pin['name']+' / '+pin['type'], record['pin_evidence'])
            for name,value in record['parameters'].items():
                append(name, value, value.get('evidence'))
        else:
            for index, anchor in enumerate(record['evidence']):
                append('Block reference '+str(index+1), anchor['source'], anchor)
            def values(label, value):
                if isinstance(value, dict):
                    if 'basis' in value or value.get('status')=='UNKNOWN':
                        append(label, value, value.get('evidence'))
                    elif not value:
                        append(label, value)
                    else:
                        for name, child in value.items():values(label+'/'+name, child)
                elif isinstance(value, list):
                    if not value:append(label, value)
                    for index, child in enumerate(value):values(label+'/'+str(index), child)
                else:
                    append(label, value)
            for name in ('parameters','ports','components','nets','checks','layout'):
                values(name, record[name])
        return {'title':record.get('mpn',record['id']),'workspace':str(self.root), 'record':record, 'rows':rows}

    def evidence(self, identity):
        catalog = Catalog(self.root, self.root/'schemas')
        return catalog.authorize_read(identity).read_bytes()
