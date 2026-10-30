"""Check that catalog authority is used by committed design graphs."""
from pathlib import Path

from pcbknowledge.serialization import read_json

AUDITED_KINDS = ('part:', 'package:', 'source:')
MAX_GRAPH_BYTES = 1_000_000


def design_inputs(root):
    """Load original reference/corpus graphs and preserved synthesis graph inputs."""
    graphs = []
    briefs = {}
    location = Path(root) / 'evals'
    for path in sorted(location.rglob('*.json')):
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise ValueError('Design input symlinks are forbidden')
        if path.stat().st_size > MAX_GRAPH_BYTES:
            raise ValueError('Oversized design audit input')
        document = read_json(path.read_bytes())
        if not isinstance(document, dict):
            continue
        schema = document.get('schema')
        if schema == 'pcbknowledge.design-brief.v2':
            identity = document['id']
            if identity in briefs and briefs[identity] != document:
                raise ValueError('Conflicting design briefs in audit inputs')
            briefs[identity] = document
        graph = document.get('graph', document)
        if isinstance(graph, dict) and graph.get('schema') == 'pcbknowledge.block-graph.v2':
            graphs.append(graph)
    return graphs, briefs


def _selection_roots(catalog, graph):
    identities = set()
    for instance in graph['instances']:
        block = catalog.records.get(instance['block'])
        if block is None:
            continue
        identities.add(block['id'])
        for component in block['components']:
            try:
                candidates = catalog._candidates(component['select'])
            except ValueError:
                continue
            identities.update(part['id'] for part in candidates)
    return identities


def audit_catalog(catalog, graphs=None, briefs=None):
    """Report orphan IDs; refusal fixtures can still demonstrate used selections."""
    from .expansion import dependency_closure, expand
    from .requirements import validate_package_requirements

    if graphs is None:
        graphs, loaded_briefs = design_inputs(catalog.root)
        briefs = loaded_briefs if briefs is None else briefs
    briefs = briefs or {}
    for brief in briefs.values():
        catalog.structure(brief, 'design-brief.schema.json')
        validate_package_requirements(catalog, brief)
        expected = brief.get('expected_refusal')
        if expected and expected['requirement'] not in {item['id'] for item in brief['functions']}:
            raise ValueError('Expected refusal must name a required function')
    if any(graph['brief'] not in briefs for graph in graphs):
        raise ValueError('Preserved graph refers to a missing brief')
    reachable = set()
    for graph in graphs:
        catalog.structure(graph, 'block-graph.schema.json')
        roots = _selection_roots(catalog, graph)
        brief = briefs.get(graph['brief'])
        if brief is not None:
            # This pure projection discovers applied rules/fab dependencies. The
            # synthetic commit is an audit input, never an acceptance receipt.
            intent = expand(catalog, graph, brief, bundle_commit='0' * 40)
            roots.update(intent['dependencies'])
        reachable.update(dependency_closure(catalog, roots))
    audited = {identity for identity in catalog.records if identity.startswith(AUDITED_KINDS)}
    unreachable = sorted(audited - reachable)
    return {
        'status': 'VALID' if not unreachable else 'INVALID',
        'graphs': len(graphs),
        'audited': len(audited),
        'reachable': sorted(audited & reachable),
        'unreachable': unreachable,
    }


def require_audit(catalog):
    result = audit_catalog(catalog)
    if result['unreachable']:
        raise ValueError('Unreachable catalog records: ' + ', '.join(result['unreachable']))
    return result
