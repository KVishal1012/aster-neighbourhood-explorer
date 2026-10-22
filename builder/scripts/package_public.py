"""Copy only validated manifests and their referenced public objects into a build."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def package(source:Path, destination:Path)->dict:
    """Audit strict content hashes and retain all complete immutable snapshots."""
    latest=json.loads((source/'latest.json').read_text())
    if not re.fullmatch(r'[a-f0-9]{20}',latest['id']):raise ValueError('Invalid latest snapshot')
    output=destination/'planning'
    output.mkdir(parents=True,exist_ok=True)
    objects=set();snapshots=[]
    for path in sorted(source.glob('*/manifest.json')):
        manifest=json.loads(path.read_text())
        if path.parent.name!=manifest['id'] or not re.fullmatch(r'[a-f0-9]{20}',manifest['id']):raise ValueError('Snapshot identity mismatch')
        if not all(manifest.get('validation',{}).values()) or not manifest.get('assets'):raise ValueError('Unvalidated snapshot')
        for logical,digest in manifest['assets'].items():
            if '..' in logical or not re.fullmatch(r'[a-f0-9]{64}',digest):raise ValueError('Invalid public asset reference')
            objects.add(digest)
        snapshots.append(manifest['id'])
        (output/manifest['id']).mkdir(exist_ok=True)
        shutil.copy2(path,output/manifest['id']/'manifest.json')
    if latest['id'] not in snapshots:raise ValueError('Latest snapshot missing')
    (output/'objects').mkdir(exist_ok=True)
    total=0
    for digest in objects:
        path=source/'objects'/f'{digest}.json.gz'
        content=gzip.decompress(path.read_bytes())
        if hashlib.sha256(content).hexdigest()!=digest:raise ValueError(f'Public object checksum mismatch: {digest}')
        total+=path.stat().st_size
        shutil.copy2(path,output/'objects'/path.name)
    if total>850_000_000:raise ValueError('Public data exceeds 850 MB publication budget; retain history and migrate hosting before publishing')
    shutil.copy2(source/'latest.json',output/'latest.json')
    (destination/'.nojekyll').touch()
    report={'snapshots':snapshots,'objects':len(objects),'compressed_bytes':total,'raw_private_files_included':False}
    (destination/'release-validation.json').write_text(json.dumps(report,indent=2))
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'public/planning')
    parser.add_argument('--destination',type=Path,default=ROOT/'dist-public')
    args=parser.parse_args();print(json.dumps(package(args.source,args.destination)))
