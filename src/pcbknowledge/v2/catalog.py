"""Read a selected workspace and validate the complete v2 reference closure."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

from pcbknowledge.serialization import canonical_json, read_json
from pcbknowledge.workspace import validate_workspace
from .schema import ContractSchemas
from .vocabulary import Vocabulary
from .footprints import derive_footprint

DIRECTORIES = {'source':'sources', 'part':'parts', 'package':'packages', 'block':'blocks',
               'rule':'rules', 'fab_profile':'fab-profiles'}
LEVELS = ('DRAFT', 'AGENT_VERIFIED', 'HUMAN_VERIFIED')
ELIGIBLE = {'PUBLIC_REFERENCE', 'OPEN_LICENSE', 'INTERNAL'}
MAX_RECORD_BYTES = 1_000_000


def selected_candidate(candidates):
    """Use expansion's verification priority and stable identity tie-break."""
    if not candidates:
        raise ValueError("No candidate matches the requested selection")
    return min(candidates, key=lambda part: (-LEVELS.index(part["verification"]), part["id"]))


def regular_bytes(root, path):
    path = Path(path)
    if not path.is_relative_to(root):
        raise ValueError('Path escapes selected workspace')
    for parent in (path, *path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError(f'Symlinks are forbidden: {path.relative_to(root)}')
    if not path.is_file() or path.stat().st_size > MAX_RECORD_BYTES:
        raise ValueError(f'Missing, unsafe or oversized record: {path}')
    return path.read_bytes()


def record_path(root, identity):
    if re.fullmatch(r'[a-z_]+:[a-z0-9][a-z0-9/_-]*', identity) is None:
        raise ValueError('Malformed record identity')
    kind, suffix = identity.split(':', 1)
    if kind not in DIRECTORIES or '//' in suffix or suffix.endswith('/'):
        raise ValueError('Unsupported record identity')
    return root/'knowledge'/DIRECTORIES[kind]/(suffix+'.json')


def unique(items, field, label):
    result = {item[field]:item for item in items}
    if len(result) != len(items):
        raise ValueError(f'Duplicate {label}')
    return result


class Catalog:
    def __init__(self, root: Path, schema_dir: Path):
        self.root = validate_workspace(root).root
        self.schemas = ContractSchemas(schema_dir)
        self.vocabulary = Vocabulary.load(self.root/'knowledge/registry', schema_dir)
        self.records = {}
        for kind, directory in DIRECTORIES.items():
            location = self.root/'knowledge'/directory
            if location.is_symlink():
                raise ValueError('Authority directory symlinks are forbidden')
            for path in sorted(location.rglob('*')):
                if path.is_dir() and not path.is_symlink():
                    continue
                if path.name == '.gitkeep' and not regular_bytes(self.root, path).strip():
                    continue
                if path.suffix != '.json':
                    raise ValueError(f'Unexpected authority file: {path}')
                payload = regular_bytes(self.root, path)
                document = read_json(payload)
                schema_name = kind.replace('_','-')+'.schema.json'
                self.structure(document, schema_name)
                if path != record_path(self.root, document['id']):
                    raise ValueError(f'Record path does not match identity: {path}')
                if payload != canonical_json(document).encode('utf-8'):
                    raise ValueError(f'Noncanonical JSON: {path}')
                if document['id'] in self.records:
                    raise ValueError('Duplicate record identity')
                self.records[document['id']] = document
        self.validate()

    def structure(self, document, schema_name):
        schema = self.schemas.load(schema_name)
        self.schemas.check(schema, schema_name)
        self.schemas.apply(document, schema, schema_name)
        self.vocabulary.document(document)

    def get(self, identity, kind=None):
        if identity not in self.records or (kind and not identity.startswith(kind+':')):
            raise ValueError(f'Missing {kind or "record"}: {identity}')
        return self.records[identity]

    def search(self, kind, text='', role=None):
        if role:
            self.vocabulary.member('roles', role)
        return [r for key,r in sorted(self.records.items()) if key.startswith(kind+':')
                and (not role or role in r.get('roles', []))
                and text.casefold() in ' '.join(
                    str(r.get(k,'')) for k in ('id','mpn','manufacturer','category')
                ).casefold()]

    def evidence(self, anchor):
        source = self.get(anchor['source'], 'source')
        if source['license_class'] not in ELIGIBLE:
            raise ValueError(f'License blocks source processing: {source["id"]}')
        if not 1 <= anchor['page'] <= source['pages']:
            raise ValueError(f'Evidence page outside source: {anchor}')

    def authorize_read(self, identity):
        source=self.get(identity, 'source')
        status=self.evidence_status(source)
        if status == 'LICENSE_BLOCKED':
            raise PermissionError('Source license blocks processing')
        if status != 'LOCALLY_VERIFIED':
            raise FileNotFoundError('NOT_LOCALLY_VERIFIED')
        digest=source['sha256']
        return self._evidence_path(source)

    def _evidence_path(self, source):
        digest = source['sha256']
        suffix = '.html' if source.get('media_type') == 'text/html' else '.pdf'
        return self.root/'.pcbknowledge/evidence/sha256'/digest[:2]/(digest + suffix)

    def evidence_status(self, source):
        """Hash only eligible local originals. Absence is an explicit result."""
        if source['license_class'] not in ELIGIBLE:
            return 'LICENSE_BLOCKED'
        digest = source['sha256']
        path = self._evidence_path(source)
        if not path.exists():
            return 'NOT_LOCALLY_VERIFIED'
        for parent in (path, *path.parents):
            if parent == self.root:
                break
            if parent.is_symlink():
                raise ValueError('Evidence symlinks are forbidden')
        if not path.is_file() or path.stat().st_size != source['bytes']:
            raise ValueError('Evidence byte size mismatch')
        payload = path.read_bytes()
        signature_valid = (
            (b'<html' in payload[:4096].lower() or b'<!doctype html' in payload[:4096].lower())
            if source.get('media_type') == 'text/html' else payload.startswith(b'%PDF-')
        )
        if hashlib.sha256(payload).hexdigest() != digest or not signature_valid:
            raise ValueError('Evidence digest or media signature mismatch')
        return 'LOCALLY_VERIFIED'

    def validate(self):
        identities = set()
        for record in self.records.values():
            provenance = record['provenance']
            actors = provenance['verified_by']
            if provenance['created_by'] in actors:
                raise ValueError('Verifier must be independent of creator')
            level = record['verification']
            required_prefix = {'AGENT_VERIFIED':'agent:', 'HUMAN_VERIFIED':'human:'}.get(level)
            if required_prefix and not any(a.startswith(required_prefix) for a in actors):
                raise ValueError(f'{level} requires an actual {required_prefix} verifier')
            self._anchors(record)
            kind = record['schema'].split('.')[1]
            if kind == 'source':
                self.evidence_status(record)
            elif kind == 'part':
                identity = (record['manufacturer'], record['mpn'])
                if identity in identities:
                    raise ValueError('Duplicate exact manufacturer/MPN identity')
                identities.add(identity)
                self._part(record)
            elif kind == 'package':
                if not record['evidence'] and record.get('generator') != 'mechanical_hole':
                    raise ValueError('Electrical packages require source evidence')
                derive_footprint(record)
            elif kind == 'block':
                self._block(record)
            elif kind == 'rule':
                if 'part' in record['applies_to']:
                    self.get(record['applies_to']['part'], 'part')
                if 'pin_type' in record['applies_to']:
                    self.vocabulary.member('pin-types', record['applies_to']['pin_type'])
        return self

    def _anchors(self, value):
        if isinstance(value, dict):
            if value.get('basis')=='CALCULATED':
                from .calculators import calculate
                outputs = calculate(value['calculator'], value['inputs'])
                expected = {k:value[k] for k in ('value','min','typ','max','unit') if k in value}
                if not any(
                    expected == {k:q[k] for k in ('value','min','typ','max','unit') if k in q}
                    for q in outputs.values()
                ):
                    raise ValueError('Calculated quantity does not match executable output')
            if 'source' in value and 'page' in value:
                self.evidence(value)
            for child in value.values():
                self._anchors(child)
        elif isinstance(value, list):
            for child in value:
                self._anchors(child)

    def _part(self, part):
        from .bootstrap import validate_part
        validate_part(part, self.evidence)
        package = self.get(part['package'], 'package')
        if part['mpn'] not in package['scope']['mpns']:
            raise ValueError(f'Part MPN is outside package drawing scope: {part["id"]}')
        if package['scope']['basis'] == 'ENGINEERING_DEFAULT':
            if 'mechanical.mounting-hole' not in part['roles']:
                raise ValueError('Engineering-default package scope is mechanical-only')
        elif part['identity_evidence'].get('source') not in {
            anchor['source'] for anchor in package['scope']['evidence']
        }:
            raise ValueError('Package scope does not cite the part identity source')
        pins = unique(part['pins'], 'number', 'part pin number')
        if part['pin_evidence']['basis'] == 'STANDARD_CONVENTION' and len(pins) != 2:
            raise ValueError('Standard terminal convention requires exactly two electrical pins')
        pads = {p['number'] for p in derive_footprint(package)['pads'] if p['kind'] != 'MECHANICAL'}
        mechanical = 'mechanical.mounting-hole' in part['roles']
        for field in ('pin_evidence', 'identity_evidence'):
            if part[field].get('basis') == 'ENGINEERING_DEFAULT' and not mechanical:
                raise ValueError('Engineering-default identity is mechanical-only')
        if not pins and not mechanical:
            raise ValueError('Electrical parts require pins')
        if set(pins) != pads:
            raise ValueError(f'Pin/pad coverage mismatch: {part["id"]}')
        from .gpio import validate_part_functions
        validate_part_functions(self, part)
        from .pin_defaults import validate_unconnected_states
        validate_unconnected_states(self, part)
        for pin in pins.values():
            alias = pin.get('same_net_as')
            if alias and (alias not in pins or alias == pin['number'] or 'same_net_as' in pins[alias]):
                raise ValueError('Pin alias must reference a distinct primary pin')
        for override in part.get('overrides', []):
            self.get(override['rule'], 'rule')

    def _candidates(self, selection):
        if 'part' in selection:
            return [self.get(selection['part'], 'part')]
        def matches(part):
            for name, limit in selection['match'].items():
                value = part['parameters'].get(name, {})
                if value.get('status') == 'UNKNOWN' or not value or limit.get('status') == 'UNKNOWN':
                    return False
                low = value.get('min', value.get('value'))
                high = value.get('max', value.get('value'))
                nominal = value.get('value', value.get('typ'))
                if value.get('unit') != limit.get('unit'):
                    return False
                if ('value' in limit and nominal != limit['value']) or ('typ' in limit and nominal != limit['typ']):
                    return False
                if any(
                    value.get('conditions', {}).get(key) != condition
                    for key, condition in limit.get('conditions', {}).items()
                ):
                    return False
                if 'min' in limit and (low is None or low < limit['min']):
                    return False
                if 'max' in limit and (high is None or high > limit['max']):
                    return False
            return True
        candidates = [p for p in self.search('part', role=selection['role']) if matches(p)]
        if not candidates:
            raise ValueError('Unsatisfiable part selection')
        return candidates

    def _block(self, block):
        ports = unique(block['ports'], 'name', 'block port name')
        for port in ports.values():
            self.vocabulary.member('pin-types', port['kind'])
        components = unique(block['components'], 'ref', 'block component ref')
        candidates = {ref:self._candidates(c['select']) for ref,c in components.items()}
        unique(block['nets'], 'name', 'block net name')
        connected = set()
        for net in block['nets']:
            for endpoint in net['connect']:
                if endpoint in connected:
                    raise ValueError('Block endpoint connected more than once')
                connected.add(endpoint)
                if endpoint.startswith('port:'):
                    if endpoint[5:] not in ports:
                        raise ValueError('Dangling block port')
                else:
                    ref, marker, name = endpoint.partition('.pin:')
                    if not marker or ref not in candidates:
                        raise ValueError('Dangling block component')
                    for part in candidates[ref]:
                        matches = [p for p in part['pins'] if p['name'] == name or p['number'] == name]
                        if not matches:
                            raise ValueError('Dangling block pin')
        if any('port:'+name not in connected for name in ports):
            raise ValueError('Unconnected block port')
        from .power_sinks import validate_block_loads
        validate_block_loads(self, block, candidates)
        from .calculators import validate_inputs
        for check in block['checks']:
            validate_inputs(check['calculator'], check['inputs'], allow_parameters=True)
            limit = check['require']['limit']
            if set(limit) == {'parameter'} and limit['parameter'] not in block['parameters']:
                raise ValueError('Dangling calculator limit parameter')
            for value in check['inputs'].values():
                if set(value) == {'parameter'} and value['parameter'] not in block['parameters']:
                    raise ValueError('Dangling calculator block parameter')
                if set(value) in ({'component', 'parameter'}, {'component', 'parameter', 'bound'}):
                    if value['component'] not in candidates or any(
                        value['parameter'] not in p['parameters'] for p in candidates[value['component']]
                    ):
                        raise ValueError('Dangling calculator component parameter')
        from .kelvin_contract import block_connections, validate_kelvin
        for constraint in block['layout']:
            self._layout_references(constraint, candidates, set(n['name'] for n in block['nets']))
            if constraint['kind'] == 'KELVIN' and 'branches' in constraint:
                validate_kelvin(constraint, candidates, block_connections(block, candidates))

    @staticmethod
    def _layout_references(constraint, components, nets):
        from .reference_paths import validate_reference_path
        validate_reference_path(constraint, nets)
        if constraint.get('datum') == 'COPPER_EDGE':
            if '.pin:' in constraint['subject'] or '.pin:' not in constraint['target']:
                raise ValueError('COPPER_EDGE requires a subject component and exact target pin')
        from .kelvin_contract import validate_kelvin
        validate_kelvin(constraint, components)
        for field in ('subject','target','subjects','path'):
            values = constraint.get(field, [])
            for value in [values] if isinstance(values,str) else values:
                ref, marker, pin = value.partition('.pin:')
                if ref not in components:
                    raise ValueError(f'Dangling layout component: {value}')
                if constraint.get('datum') == 'COPPER_EDGE' and field == 'target':
                    if any(not any(p['number'] == pin for p in part['pins']) for part in components[ref]):
                        raise ValueError('COPPER_EDGE requires a physical pin number: ' + value)
                if marker and any(not any(p['number']==pin or p['name']==pin for p in part['pins'])
                                  for part in components[ref]):
                    raise ValueError(f'Dangling layout pin: {value}')
        for field in ('net','sense_nets','nets','guard_net','return_net'):
            values = constraint.get(field, [])
            for value in [values] if isinstance(values,str) else values:
                if value not in nets:
                    raise ValueError(f'Dangling layout net: {value}')
