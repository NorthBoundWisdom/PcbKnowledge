"""Entry point run only through the configured external KiCad Python interpreter."""
import argparse
import hashlib
import json
from pathlib import Path


def prepare(root, source, history_path, intent_path, bundle_path, output):
    from pcbknowledge.v2.kicad_bridge import _path
    from pcbknowledge.v2.bundle import Bundle
    from .fanout_history import propose_history
    from .fanout_emit import emit
    source = _path(root, source, exists=True)
    history_path = _path(root, history_path, exists=True)
    intent_path = _path(root, intent_path, exists=True)
    bundle_path = _path(root, bundle_path, exists=True)
    output = _path(root, output)
    if output.exists():
        raise ValueError('Fanout preparation output directory must be fresh')
    intent = json.loads(intent_path.read_text())
    bundle = Bundle(bundle_path)
    from .expansion import validate_expansion
    graph_path = _path(root, source.parent / 'graph.json', exists=True)
    authority_files = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in (graph_path, intent_path, bundle_path, history_path)}
    validate_expansion(bundle, intent, json.loads(graph_path.read_text()))
    history = json.loads(history_path.read_text())
    proposal = propose_history(root, source, history, intent, bundle.catalog,
                               placed_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in authority_files.items()):
        raise ValueError('Fanout preparation authority changed')
    output.mkdir()
    receipt = emit(root, source, proposal, output / 'seed.kicad_pcb')
    for filename, document in [('proposal.json', proposal), ('seed-receipt.json', receipt)]:
        (output / filename).write_text(json.dumps(document, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser()
    for argument in ('root', 'source', 'history', 'intent', 'bundle', 'output'):
        parser.add_argument(argument)
    arguments = parser.parse_args()
    receipt = prepare(arguments.root, arguments.source, arguments.history, arguments.intent,
                      arguments.bundle, arguments.output)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
