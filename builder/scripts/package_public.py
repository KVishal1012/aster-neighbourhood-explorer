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

def startup_payload(manifest:dict, read, put)->dict | None:
    """Derive search-only routing from a verified snapshot; omit all geometry."""
    routes = manifest.get('address_search', {})
    if not manifest.get('regional') or not routes:
        return None
    catalogs = {}
    for municipality, route in routes.items():
        if route.get('format') == 'legacy-prefix':
            continue
        index = read(route['index'])
        if route.get('format') == 'legacy-address-matches':
            catalog = {'format':'matches', 'buckets':{key:manifest['assets'][path] for key,path in index.items()}}
        else:
            catalog = {'format':'sorted', **{field:[{**item,'digest':manifest['assets'][item['path']]} for item in index[field]] for field in ('street','search_label')}}
        catalogs[municipality] = put(catalog)
    return {'version':1, 'snapshot':{**manifest,'assets':{key:value for key,value in manifest['assets'].items() if key=='exclusions.json'},'tiles':{}},
            'municipalities':[{key:value for key,value in row.items() if key not in ('geometry','metric')} for row in read('municipalities.json')],
            'neighbourhoods':[{key:row[key] for key in ('id','label','lon','lat')} for row in read('neighbourhoods.json')],
            'catalogs':catalogs}

def package(source:Path, destination:Path)->dict:
    """Audit strict content hashes and retain all complete immutable snapshots."""
    latest=json.loads((source/'latest.json').read_text())
    if not re.fullmatch(r'[a-f0-9]{20}',latest['id']):raise ValueError('Invalid latest snapshot')
    output=destination/'planning'
    output.mkdir(parents=True,exist_ok=True)
    objects=set();snapshots=[];manifests=[]
    for path in sorted(source.glob('*/manifest.json')):
        manifest=json.loads(path.read_text())
        if path.parent.name!=manifest['id'] or not re.fullmatch(r'[a-f0-9]{20}',manifest['id']):raise ValueError('Snapshot identity mismatch')
        if not all(manifest.get('validation',{}).values()) or not manifest.get('assets'):raise ValueError('Unvalidated snapshot')
        for logical,digest in manifest['assets'].items():
            if '..' in logical or not re.fullmatch(r'[a-f0-9]{64}',digest):raise ValueError('Invalid public asset reference')
            objects.add(digest)
        snapshots.append(manifest['id']);manifests.append(manifest)
        (output/manifest['id']).mkdir(exist_ok=True)
        shutil.copy2(path,output/manifest['id']/'manifest.json')
        # Explicit gzip also works on static hosts without Content-Encoding.
        (output/manifest['id']/'manifest.json.gz').write_bytes(gzip.compress(path.read_bytes(), mtime=0))
    if latest['id'] not in snapshots:raise ValueError('Latest snapshot missing')
    (output/'objects').mkdir(exist_ok=True)
    total=0
    for digest in objects:
        path=source/'objects'/f'{digest}.json.gz'
        content=gzip.decompress(path.read_bytes())
        if hashlib.sha256(content).hexdigest()!=digest:raise ValueError(f'Public object checksum mismatch: {digest}')
        total+=path.stat().st_size
        shutil.copy2(path,output/'objects'/path.name)
    # Derived catalogs retain exact object hashes from the audited source manifest.
    derived = set()
    def put(value):
        raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
        digest=hashlib.sha256(raw).hexdigest()
        target=output/'objects'/f'{digest}.json.gz'
        if digest not in objects and digest not in derived:
            target.write_bytes(gzip.compress(raw,mtime=0));derived.add(digest)
        return digest
    for manifest in manifests:
        def read(logical):
            return json.loads(gzip.decompress((output/'objects'/f"{manifest['assets'][logical]}.json.gz").read_bytes()))
        startup=startup_payload(manifest,read,put)
        if startup is not None:
            raw=json.dumps(startup,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
            payload=gzip.compress(raw,mtime=0)
            (output/manifest['id']/'startup-v1.json.gz').write_bytes(payload)
            total+=len(payload)
    total+=sum((output/'objects'/f'{digest}.json.gz').stat().st_size for digest in derived)
    objects.update(derived)
    if total>850_000_000:raise ValueError('Public data exceeds 850 MB publication budget; retain history and migrate hosting before publishing')
    shutil.copy2(source/'latest.json',output/'latest.json')
    (destination/'.nojekyll').touch()
    # Transport is a separate, lazily fetched public snapshot family.
    import sys
    sys.path.insert(0,str(ROOT))
    from scripts.build_transport import package_transport
    transport=package_transport(source.parent/'transport',output/'transport')
    if total+transport.get('bytes',0)>850_000_000:raise ValueError('Combined public package exceeds 850 MB budget')
    report={'transport':transport,'snapshots':snapshots,'objects':len(objects),'compressed_bytes':total,'raw_private_files_included':False}
    (destination/'release-validation.json').write_text(json.dumps(report,indent=2))
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'public/planning')
    parser.add_argument('--destination',type=Path,default=ROOT/'dist-public')
    args=parser.parse_args();print(json.dumps(package(args.source,args.destination)))
