"""Evaluate preserved, independently authored graphs against a pinned catalog."""
from __future__ import annotations

import hashlib

from pcbknowledge.serialization import canonical_json
from .expansion import expand, validate_expansion


def digest(document):
    return hashlib.sha256(canonical_json(document).encode()).hexdigest()


def topology(graph):
    """Ignore net/instance labels, not functions, blocks or electrical endpoints."""
    identities = {item['id']: canonical_json({'block': item['block'],
                  'requirements': sorted(item['requirements'])})
                  for item in graph['instances']}
    blocks = sorted(identities.values())
    nets = []
    for connection in graph['connections']:
        endpoints = []
        for endpoint in connection['endpoints']:
            instance, port = endpoint['instance'], endpoint['port']
            if instance not in identities:
                raise ValueError('Invalid graph endpoint')
            endpoints.append((identities[instance], port))
        nets.append(sorted(endpoints))
    return {'blocks': blocks, 'nets': sorted(nets)}


def evaluate(bundle, reference, attempts):
    """Consume actual agent outputs, never synthesize or relabel a reference copy.

    Independence receipts are attestations of the orchestration process, not a
    claim that a JSON file can prove which model authored it. Distinct agents and
    output hashes, recorded input hashes, and a separate reviewer are required.
    """
    if not isinstance(attempts, list):
        raise ValueError('Attempts must be a list of preserved graph receipts')
    for attempt in attempts:
        if not isinstance(attempt, dict) or not isinstance(attempt.get('graph'), dict) or not isinstance(attempt.get('receipt'), dict):
            raise ValueError('Attempt must contain graph and receipt objects')
        receipt = attempt['receipt']
        if any(not isinstance(receipt.get(key), str) for key in ('agent','reviewer','bundle_commit','graph_sha256','brief_sha256')):
            raise ValueError('Synthesis receipt fields must be strings')
        bundle.catalog.structure(attempt['graph'], 'block-graph.schema.json')
    reference_intent = expand(bundle.catalog, reference, bundle.briefs[reference['brief']],
                              bundle_commit=bundle.commit)
    validate_expansion(bundle, reference_intent, reference)
    expected = topology(reference)
    if len(attempts) < 3:
        raise ValueError('At least three independent synthesis attempts are required')
    actors, outputs = set(), set()
    results = []
    for attempt in attempts:
        graph, receipt = attempt['graph'], attempt['receipt']
        actor = receipt['agent']
        graph_hash = digest(graph)
        brief = bundle.briefs[graph['brief']]
        if (not actor.startswith('agent:') or actor in actors or graph_hash in outputs
                or graph_hash == digest(reference)):
            raise ValueError('Attempts require distinct actual agents and original graph outputs')
        if (receipt['bundle_commit'] != bundle.commit or receipt['graph_sha256'] != graph_hash
                or receipt['brief_sha256'] != digest(brief)
                or receipt.get('reference_accessed') is not False
                or not receipt.get('reviewer', '').startswith('agent:')
                or receipt['reviewer'] == actor):
            raise ValueError('Invalid synthesis independence receipt')
        actors.add(actor); outputs.add(graph_hash)
        intent = expand(bundle.catalog, graph, brief, bundle_commit=bundle.commit)
        same = topology(graph) == expected
        equivalent = receipt.get('equivalence_review')
        accepted_equivalence = (isinstance(equivalent, str) and bool(equivalent.strip()))
        passed = intent['status'] == 'EXPANDED' and (same or accepted_equivalence)
        results.append({'agent': actor, 'graph_sha256': graph_hash,
                        'status': intent['status'], 'a2': passed,
                        'reference_equivalent': same or accepted_equivalence,
                        'equivalence_review': equivalent if not same else None,
                        'checks': len(intent['checks']), 'refusals': intent['refusals']})
    passed = sum(item['a2'] for item in results)
    return {'status': 'PASS' if passed >= 2 else 'FAIL', 'bundle_commit': bundle.commit,
            'reference_status': reference_intent['status'], 'attempts': results,
            'passed': passed, 'total': len(results), 'required': 2}
