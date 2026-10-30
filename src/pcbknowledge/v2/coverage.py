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


def graph_coverage(catalog, brief, graph):
    """Replay one current-input graph without hiding its readiness or failures."""
    from .expansion import expand
    instances = graph.get('instances', [])
    readiness = {'ready': 0, 'total': len(instances) if isinstance(instances, list) else 0}
    try:
        readiness = coverage(catalog, graph)
        intent = expand(catalog, graph, brief, bundle_commit='0' * 40)
        status, refusals = intent['status'], intent['refusals']
    except (ValueError, KeyError, TypeError) as error:
        status = 'REFUSED'
        refusals = [{'code': 'INVALID_REFERENCE', 'path': 'graph',
                     'reason': str(error)[:256], 'queries': ['Q10']}]
    return {'graph': graph['id'], 'ready': readiness['ready'], 'total': readiness['total'],
            'status': status, 'refusals': refusals}


def brief_coverage(catalog, identity, brief, graphs):
    from .requirements import assess_brief
    refusals = assess_brief(catalog, brief)
    expected = brief.get('expected_refusal')
    if expected and expected['requirement'] not in {item['id'] for item in brief['functions']}:
        raise ValueError('Expected refusal must name a required function')
    results = [graph_coverage(catalog, brief, graph) for graph in graphs if graph['brief'] == identity]
    complete = bool(results) and all(item['status'] == 'EXPANDED' and item['ready'] == item['total']
                                     for item in results)
    status = 'NOT_RUN' if not results else 'READY' if complete and not refusals else 'INCOMPLETE'
    return {'brief': identity, 'status': status, 'graphs': results, 'expected_refusal': expected,
            'screening': 'REFUSED' if refusals else 'ELIGIBLE', 'refusals': refusals,
            'graph_readiness': 'NOT_RUN' if not results else 'EXPANDED' if complete else 'REFUSED',
            'graph_refusals': [refusal for item in results for refusal in item['refusals']],
            'blocks_ready': sum(item['ready'] for item in results),
            'blocks_total': sum(item['total'] for item in results),
            'remaining': [] if results else ['No preserved block graph']}


def coverage_all(catalog, briefs=None, graphs=None):
    """Screen every brief and replay every graph; this is not a synthesis receipt."""
    from .audit import design_inputs, require_audit
    if briefs is None:
        require_audit(catalog)
        graphs, briefs = design_inputs(catalog.root)
    graphs = [] if graphs is None else graphs
    if any(graph['brief'] not in briefs for graph in graphs):
        raise ValueError('Preserved graph refers to a missing brief')
    rows = [brief_coverage(catalog, identity, brief, graphs) for identity, brief in sorted(briefs.items())]
    return {'schema': 'pcbknowledge.corpus-coverage.v2',
            'status': 'READY' if rows and all(row['status'] == 'READY' for row in rows) else 'INCOMPLETE',
            'briefs': rows,
            'scope': 'Eligibility screening and current-input graph replay only; no new A2 or synthesis proof'}
