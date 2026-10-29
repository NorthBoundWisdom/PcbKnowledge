"""Read-only JSON queries over a validated selected workspace."""
from __future__ import annotations

import argparse
import json
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
    for name in ('part','package','block','fab','registry'):
        actions=groups.add_parser(name).add_subparsers(dest='action',required=True)
        show=actions.add_parser('show');show.add_argument('id')
        if name in ('part','block'):
            search=actions.add_parser('search');search.add_argument('--text',default='')
            if name=='part':search.add_argument('--role')
    return result


def main(argv=None):
    arguments=parser().parse_args(argv)
    try:
        root=validate_workspace(arguments.repo).root
        catalog=Catalog(root, SCHEMA_DIR)
        group=arguments.group
        if group=='v2':
            result={'status':'VALID','records':len(catalog.records),'evidence':{
                r['id']:catalog.evidence_status(r) for r in catalog.search('source')}}
        elif group=='registry':
            name=arguments.id.removeprefix('registry:')
            if name not in catalog.vocabulary.entries:raise ValueError('Unknown registry')
            result={'id':'registry:'+name,'entries':catalog.vocabulary.entries[name]}
        elif arguments.action=='show':
            result=catalog.get(arguments.id, 'fab_profile' if group=='fab' else group)
        else:
            result=catalog.search(group,arguments.text,getattr(arguments,'role',None))
        print(json.dumps(result,ensure_ascii=False,sort_keys=True,allow_nan=False))
        return 0
    except (OSError,ValueError,RuntimeError) as error:
        print(json.dumps({'status':'ERROR','message':str(error)},sort_keys=True))
        return 2
