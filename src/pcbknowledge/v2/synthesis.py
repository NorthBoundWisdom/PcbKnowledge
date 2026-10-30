"""Evaluate preserved, independently authored graphs against a pinned catalog."""
from __future__ import annotations

import hashlib

from pcbknowledge.serialization import canonical_json
from .expansion import expand, validate_expansion
from .synthesis_identity import engine_digest, input_identity, receipt_identity


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


def _evaluate_graphs(bundle, reference, attempts, *, content_identified, replay=False):
    """Consume actual agent outputs, never synthesize or relabel a reference copy.

    Independence receipts are attestations of the orchestration process, not a
    claim that a JSON file can prove which model authored it. Distinct agents and
    output hashes, recorded input hashes, and a separate reviewer are required.
    """
    if not isinstance(attempts, list):
        raise ValueError('Attempts must be a list of preserved graph receipts')
    for attempt in attempts:
        if (not isinstance(attempt, dict) or not isinstance(attempt.get('graph'), dict)
                or not isinstance(attempt.get('receipt'), dict)):
            raise ValueError('Attempt must contain graph and receipt objects')
        receipt = attempt['receipt']
        if not content_identified and ('format' in receipt or 'input_identity' in receipt):
            raise ValueError('Content-identified receipts require current corpus evaluation')
        if any(not isinstance(receipt.get(key), str)
               for key in ('agent','reviewer','bundle_commit','graph_sha256','brief_sha256')):
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
        if content_identified:
            receipt_identity(bundle, receipt, replay=replay)
        if ((not content_identified and receipt['bundle_commit'] != bundle.commit)
                or receipt['graph_sha256'] != graph_hash
                or receipt['brief_sha256'] != digest(brief)
                or receipt.get('reference_accessed') is not False
                or not receipt.get('reviewer', '').startswith('agent:')
                or receipt['reviewer'] == actor):
            raise ValueError('Invalid synthesis independence receipt')
        actors.add(actor)
        outputs.add(graph_hash)
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


def evaluate(bundle, reference, attempts):
    """Replay legacy G1 receipts; new synthesis uses evaluate_corpus."""
    return _evaluate_graphs(bundle, reference, attempts, content_identified=False)


def _text_digest(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Preserved skill and transcript text must be nonempty strings')
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _transcript_digest(transcript):
    if not isinstance(transcript, (dict, list)) or not transcript:
        raise ValueError('Preserved query transcript must be a nonempty object or list')
    return digest(transcript)


def _corpus_receipts(bundle, brief, attempts, *, orchestrator, skill_text, bundle_sha256, negative, historical, replay):
    if not isinstance(orchestrator, str) or not orchestrator.startswith('agent:'):
        raise ValueError('Corpus evaluation requires an explicit orchestrator identity')
    if not isinstance(attempts, list) or len(attempts) != 3:
        raise ValueError('Corpus evaluation requires exactly three fresh attempts')
    if (not isinstance(bundle_sha256, str) or len(bundle_sha256) != 64
            or any(character not in '0123456789abcdef' for character in bundle_sha256)):
        raise ValueError('Corpus evaluation requires the actual bundle file SHA-256')
    authors = set()
    for attempt in attempts:
        if not isinstance(attempt, dict) or not isinstance(attempt.get('receipt'), dict):
            raise ValueError('Malformed corpus attempt receipt')
        actor = attempt['receipt'].get('agent')
        if not isinstance(actor, str) or not actor.startswith('agent:') or actor in authors or actor == orchestrator:
            raise ValueError('Corpus authors must be distinct fresh agents, not the orchestrator')
        authors.add(actor)
    key = 'refusal' if negative else 'graph'
    expected = {'brief_sha256': digest(brief), 'skill_sha256': _text_digest(skill_text),
                'orchestrator': orchestrator, 'reference_accessed': False, 'mode': 'QUERY_MEDIATED'}
    if historical:
        expected.update(bundle_commit=bundle.commit, bundle_sha256=bundle_sha256)
    for attempt in attempts:
        receipt = attempt['receipt']
        if historical and ('format' in receipt or 'input_identity' in receipt):
            raise ValueError('Historical mode accepts only preserved commit-only receipts')
        if not historical:
            receipt_identity(bundle, receipt, replay=replay)
            if receipt['input_identity'] != attempts[0]['receipt']['input_identity']:
                raise ValueError('Corpus attempts must share the same original input identity')
        reviewer = receipt.get('reviewer')
        if (not isinstance(reviewer, str) or not reviewer.startswith('agent:')
                or reviewer in authors or reviewer == orchestrator):
            raise ValueError('Corpus reviewer must be independent of every author and orchestrator')
        if not isinstance(attempt.get(key), dict) or ('graph' in attempt if negative else 'refusal' in attempt):
            raise ValueError('Corpus attempt must contain only the requested graph or refusal output')
        checks = {**expected, key + '_sha256': digest(attempt[key]),
                  'transcript_sha256': _transcript_digest(attempt.get('transcript'))}
        if any(receipt.get(name) != value for name, value in checks.items()):
            raise ValueError('Corpus receipt does not match exact preserved inputs/output')
        if receipt.get('reference_accessed') is not False:
            raise ValueError('Reference access is prohibited during corpus synthesis')
        if not negative and receipt.get('reviewer_verdict') not in ('EQUIVALENT', 'NOT_EQUIVALENT'):
            raise ValueError('Positive corpus receipt requires an explicit controlled reviewer verdict')
        review = receipt.get('equivalence_review')
        if not isinstance(review, str) or not review.strip():
            raise ValueError('Corpus outputs require an explicit independent review statement')


def corpus_topology(graph):
    """Conservative labeled structure; duplicate signatures require independent equivalence review.

    Never equate repeated block instances by collapsing them into one signature.
    This is deliberately not a full graph-isomorphism solver.
    """
    identities = {}
    for item in graph['instances']:
        signature = canonical_json({
            'block': item['block'], 'requirements': sorted(item['requirements']),
            'parameters': item.get('parameters', {}),
            'ports': sorted(item.get('ports', []), key=canonical_json),
        })
        if item['id'] in identities:
            raise ValueError('Duplicate corpus graph instance identity')
        identities[item['id']] = signature
    if len(set(identities.values())) != len(identities):
        return None
    nets = []
    for connection in graph['connections']:
        endpoints = []
        for endpoint in connection['endpoints']:
            if endpoint['instance'] not in identities:
                raise ValueError('Invalid corpus graph endpoint')
            endpoints.append((identities[endpoint['instance']], endpoint['port']))
        nets.append(sorted(endpoints))
    return {'instances': sorted(identities.values()), 'nets': sorted(nets),
            'requirements': sorted(graph.get('requirements', []), key=canonical_json)}


def _positive_corpus(bundle, brief, attempts, reference, *, historical, replay):
    if not isinstance(reference, dict) or reference.get('brief') != brief['id']:
        raise ValueError('Positive corpus reference must match the requested brief')
    if any(attempt['graph'].get('brief') != brief['id'] for attempt in attempts):
        raise ValueError('Corpus attempt brief differs from reference/benchmark brief')
    # Reuse replay and distinct graph checks without changing historical G1 receipts.
    reference_structure = corpus_topology(reference)
    result = _evaluate_graphs(bundle, reference, attempts, content_identified=not historical, replay=replay)
    for row, attempt in zip(result['attempts'], attempts):
        verdict = attempt['receipt']['reviewer_verdict']
        structure = corpus_topology(attempt['graph'])
        row['structural_match'] = (reference_structure is not None and structure is not None
                                   and reference_structure == structure)
        row['structural_comparison'] = ('AMBIGUOUS_REPEATED_SIGNATURE'
                                        if reference_structure is None or structure is None else 'COMPARED')
        row['equivalence_review'] = attempt['receipt']['equivalence_review']
        row['reviewer_verdict'] = verdict
        row['a2'] = row['a2'] and verdict == 'EQUIVALENT'
        row['reference_equivalent'] = verdict == 'EQUIVALENT'
    result['passed'] = sum(row['a2'] for row in result['attempts'])
    result['status'] = 'PASS' if result['passed'] >= result['required'] else 'FAIL'
    if result['reference_status'] != 'EXPANDED':
        result['status'] = 'FAIL'
    return result


def _negative_corpus(bundle, brief, attempts, expected):
    from .requirements import assess_brief

    if not isinstance(expected, dict) or any(not isinstance(expected.get(k), str) for k in ('code', 'path')):
        raise ValueError('Negative corpus requires an expected refusal code and path')
    refusals = assess_brief(bundle.catalog, brief)
    reproducible = any(item.get('code') == expected['code'] and item.get('path') == expected['path']
                       for item in refusals)
    results = []
    for attempt in attempts:
        refusal = attempt['refusal']
        valid = (set(refusal) == {'brief', 'code', 'path', 'reason'} and refusal['brief'] == brief['id']
                 and refusal['code'] == expected['code'] and refusal['path'] == expected['path']
                 and isinstance(refusal['reason'], str) and bool(refusal['reason'].strip()))
        results.append({'agent': attempt['receipt']['agent'], 'refusal_sha256': digest(refusal),
                        'status': 'REFUSED' if valid and reproducible else 'INVALID_REFUSAL',
                        'correct_refusal': valid and reproducible})
    passed = sum(item['correct_refusal'] for item in results)
    return {'status': 'PASS' if passed == 3 else 'FAIL', 'bundle_commit': bundle.commit,
            'attempts': results, 'passed': passed, 'total': 3, 'required': 3,
            'replayed_refusals': refusals}


def _evaluate_corpus(bundle, brief_id, attempts, reference, expected_refusal, *,
                     orchestrator, skill_text, bundle_sha256, historical, replay):
    """Evaluate fresh benchmark receipts; provenance remains an attestation, not agent identity proof.

    Caller supplies the SHA-256 of the actual validated bundle bytes and actual
    skill text. Preserved transcript objects use canonical JSON hashes; query
    mediation is an attested workflow, not a hard-sandbox guarantee.
    Negative outputs are independently reproduced, not accepted for plausible prose.
    """
    if brief_id not in bundle.briefs:
        raise ValueError('Unknown corpus brief')
    negative = expected_refusal is not None
    if negative and reference is not None:
        raise ValueError('Negative corpus evaluation must not receive a reference graph')
    brief = bundle.briefs[brief_id]
    _corpus_receipts(bundle, brief, attempts, orchestrator=orchestrator, skill_text=skill_text,
                     bundle_sha256=bundle_sha256, negative=negative, historical=historical, replay=replay)
    result = (_negative_corpus(bundle, brief, attempts, expected_refusal) if negative
              else _positive_corpus(bundle, brief, attempts, reference, historical=historical, replay=replay))
    return {**result, 'brief': brief_id, 'mode': 'negative' if negative else 'positive',
            'orchestrator': orchestrator, 'bundle_sha256': bundle_sha256,
            'evaluation_engine_sha256': engine_digest(),
            'receipt_identity': ('HISTORICAL_COMMIT' if historical else
                                 'CATALOG_CONTENT_REPLAY' if replay else 'CATALOG_CONTENT'),
            'input_identity': None if historical else dict(attempts[0]['receipt']['input_identity']),
            'evaluation_input_identity': input_identity(bundle) if not historical else None,
            'reference_sha256': None if reference is None else digest(reference),
            'original_bundles': [{'agent': item['receipt']['agent'],
                                  'commit': item['receipt']['bundle_commit'],
                                  'sha256': item['receipt']['bundle_sha256']} for item in attempts]}


def evaluate_corpus(bundle, brief_id, attempts, reference=None, expected_refusal=None, *,
                    orchestrator, skill_text, bundle_sha256):
    """Evaluate current content-identified receipts; commit changes alone do not invalidate them."""
    return _evaluate_corpus(bundle, brief_id, attempts, reference, expected_refusal,
                            orchestrator=orchestrator, skill_text=skill_text,
                            bundle_sha256=bundle_sha256, historical=False, replay=False)


def evaluate_historical_corpus(bundle, brief_id, attempts, reference=None, expected_refusal=None, *,
                               orchestrator, skill_text, bundle_sha256):
    """Replay preserved commit-only receipts explicitly, reporting the current evaluator identity."""
    return _evaluate_corpus(bundle, brief_id, attempts, reference, expected_refusal,
                            orchestrator=orchestrator, skill_text=skill_text,
                            bundle_sha256=bundle_sha256, historical=True, replay=False)


def replay_corpus(bundle, brief_id, attempts, reference=None, expected_refusal=None, *,
                  orchestrator, skill_text, bundle_sha256):
    """Re-evaluate prior v2 receipts with current code, retaining both engine identities."""
    return _evaluate_corpus(bundle, brief_id, attempts, reference, expected_refusal,
                            orchestrator=orchestrator, skill_text=skill_text,
                            bundle_sha256=bundle_sha256, historical=False, replay=True)
