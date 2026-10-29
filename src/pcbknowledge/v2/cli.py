"""Read-only JSON queries over a validated selected workspace."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from pcbknowledge.git_native.workspace import validate_workspace
from .catalog import Catalog
from .schema import SCHEMA_DIR


def parser():
    result=argparse.ArgumentParser(description=__doc__)
    result.add_argument('--repo',type=Path,default=Path('.'))
    groups=result.add_subparsers(dest='group',required=True)
    v2=groups.add_parser('v2').add_subparsers(dest='action',required=True)
    v2.add_parser('validate')
    footprint = groups.add_parser('footprint').add_subparsers(dest='action', required=True)
    export = footprint.add_parser('export')
    export.add_argument('--output', type=Path, default=Path('build/footprints/pcbknowledge.pretty'))
    groups.add_parser('change-scope')
    for name in ('source','part','package','block','fab','registry'):
        actions=groups.add_parser(name).add_subparsers(dest='action',required=True)
        show=actions.add_parser('show');show.add_argument('id')
        if name=='source':
            authorize=actions.add_parser('authorize-read');authorize.add_argument('id')
        if name in ('part','block'):
            search=actions.add_parser('search');search.add_argument('--text',default='')
            if name=='part':search.add_argument('--role')
    return result


def main(argv=None):
    arguments=parser().parse_args(argv)
    try:
        root=validate_workspace(arguments.repo).root
        if arguments.group=='change-scope':
            def git(*args):
                return subprocess.check_output(['git','-C',str(root),*args]).decode('utf-8').split('\0')
            paths=[p for p in git('diff','--cached','--name-only','--no-renames','-z') if p]
            if not paths:
                paths=[p for p in git('diff','--name-only','--no-renames','-z')+git('ls-files','--others','--exclude-standard','-z') if p]
            data=any(p.startswith(('knowledge/','evidence/')) for p in paths)
            code=any(not p.startswith(('knowledge/','evidence/')) for p in paths)
            scope='MIXED' if data and code else 'DATA_ONLY' if data else 'CODE_ONLY' if code else 'CLEAN'
            print(json.dumps({'scope':scope,'valid_for_single_commit':scope!='MIXED'},sort_keys=True))
            return 2 if scope=='MIXED' else 0
        catalog=Catalog(root, root/'schemas')
        group=arguments.group
        if group == 'footprint':
            from .footprints import export_library
            output = arguments.output.resolve()
            build = (root / 'build').resolve()
            if not output.is_relative_to(build):
                raise ValueError('Derived footprints must be written under build/')
            files = export_library(catalog.search('package'), output)
            result = {'status': 'EXPORTED', 'files': [str(path) for path in files]}
        elif group=='v2':
            result={'status':'VALID','records':len(catalog.records),'evidence':{
                r['id']:catalog.evidence_status(r) for r in catalog.search('source')}}
        elif group=='registry':
            name=arguments.id.removeprefix('registry:')
            if name not in catalog.vocabulary.entries:raise ValueError('Unknown registry')
            result={'id':'registry:'+name,'entries':catalog.vocabulary.entries[name]}
        elif group=='source' and arguments.action=='authorize-read':
            result={'status':'AUTHORIZED','source':arguments.id,'path':str(catalog.authorize_read(arguments.id))}
        elif arguments.action=='show':
            result=catalog.get(arguments.id, 'fab_profile' if group=='fab' else group)
        else:
            result=catalog.search(group,arguments.text,getattr(arguments,'role',None))
        print(json.dumps(result,ensure_ascii=False,sort_keys=True,allow_nan=False))
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        print(json.dumps({'status':'ERROR','message':str(error)},sort_keys=True))
        return 2
