"""Explain reference-graph readiness without inventing missing catalog records."""
from __future__ import annotations

from .catalog import LEVELS
from .expansion import dependency_closure


def coverage(catalog, graph):
    catalog.structure(graph, 'block-graph.schema.json')
    results = []
    identities = [i["id"] for i in graph["instances"]]
    duplicate_ids = {i for i in identities if identities.count(i) > 1}
    for instance in graph['instances']:
        missing = []
        selected = {}
        if instance["id"] in duplicate_ids:
            missing.append("Duplicate instance identity")
        try:
            block = catalog.get(instance['block'], 'block')
        except ValueError as error:
            missing.append(str(error))
            block = None
        if block:
            if LEVELS.index(block['verification']) < LEVELS.index('AGENT_VERIFIED'):
                missing.append(f'Unverified block: {block["id"]}')
            used = {block['id']}
            if set(instance['parameters']) - set(block['parameters']):
                missing.append('Undeclared block parameter')
            for component in block['components']:
                try:
                    candidates = catalog._candidates(component['select'])
                    selected[component['ref']] = [part['id'] for part in candidates]
                    for part in candidates:
                        used.add(part['id'])
                        for record in (part, catalog.get(part['package'], 'package')):
                            if LEVELS.index(record['verification']) < LEVELS.index('AGENT_VERIFIED'):
                                missing.append(f'Unverified dependency: {record["id"]}')
                except ValueError as error:
                    missing.append(f'{component["ref"]}: {error}')
            for name, declaration in block['parameters'].items():
                value = instance['parameters'].get(name)
                if declaration['required'] and (not value or value.get('status') == 'UNKNOWN'):
                    missing.append(f'Missing required input: {name}')
                if value:
                    try:
                        catalog.vocabulary.quantity(value, declaration['quantity'])
                    except ValueError as error:
                        missing.append(str(error))
                    numeric = lambda q: {k:q[k] for k in ('value','min','typ','max','unit') if k in q}
                    if 'fixed' in declaration and numeric(value) != numeric(declaration['fixed']):
                        missing.append(f'Fixed parameter mismatch: {name}')
            for identity in sorted(dependency_closure(catalog, used)):
                if LEVELS.index(catalog.get(identity)['verification']) < LEVELS.index('AGENT_VERIFIED'):
                    missing.append(f'Unverified closure: {identity}')
            declared = {p['name']: p['kind'] for p in block['ports']}
            provided = {p['name']: p['type'] for p in instance['ports']}
            if declared != provided or len(provided) != len(instance['ports']):
                missing.append('Graph ports differ from block contract')
        results.append({'instance': instance['id'], 'block': instance['block'],
                        'ready': not missing, 'selections': selected, 'remaining': missing})
    ready = sum(row['ready'] for row in results)
    return {'status': 'READY' if ready == len(results) else 'INCOMPLETE',
            'ready': ready, 'total': len(results),
            'percent': round(100*ready/len(results), 2) if results else 100,
            'instances': results}
