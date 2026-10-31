"""Build a bounded, provenance-preserving TTC proximity and hourly schedule snapshot.

Inputs are a complete GTFS ZIP plus the archived official licence/catalogue receipt.
No arrival predictions, walk routing, frequency interpolation or live data are inferred.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,re,shutil
from datetime import datetime
from collections import Counter,defaultdict
from pathlib import Path
from zipfile import ZipFile
from pyproj import Transformer

ROOT=Path(__file__).resolve().parents[1]

def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def hour(value):
    if not re.fullmatch(r'\d{2}:\d{2}:\d{2}',value):raise ValueError('Invalid GTFS departure time')
    h,m,s=map(int,value.split(':'))
    if h>71 or m>59 or s>59:raise ValueError('Unsupported GTFS departure time')
    return h

def unique(rows,key):
    result={}
    for row in rows:
        if not row.get(key) or row[key] in result:raise ValueError('Missing or duplicate '+key)
        result[row[key]]=row
    return result

def build(source:Path,output:Path):
    receipt=json.loads((source/'receipt.json').read_text())
    digest=hashlib.sha256((source/'merged.zip').read_bytes()).hexdigest()
    if digest!=receipt['sha256'] or not receipt['stable_reread']:raise ValueError('Unverified source archive')
    for name,expected in receipt['evidence'].items():
        if hashlib.sha256((source/name).read_bytes()).hexdigest()!=expected:raise ValueError('Licence/catalogue evidence mismatch')
    z=ZipFile(source/'merged.zip')
    if z.testzip() is not None:raise ValueError('Incomplete ZIP')
    if len(z.namelist())!=len(set(z.namelist())):raise ValueError('Duplicate ZIP members')
    def rows(name):
        if name not in z.namelist():return iter(())
        return csv.DictReader(io.TextIOWrapper(z.open(name),encoding='utf-8-sig',newline=''))
    for name in ('stops.txt','routes.txt','trips.txt','stop_times.txt','agency.txt','feed_info.txt'):
        if name not in z.namelist():raise ValueError('Required file missing: '+name)
    if list(rows('frequencies.txt')):raise ValueError('Frequency-based service requires a separately reviewed adapter')
    agencies=list(rows('agency.txt'))
    if not agencies or any(r['agency_timezone']!='America/Toronto' for r in agencies):raise ValueError('Unsupported agency timezone')
    stops=unique(rows('stops.txt'),'stop_id');routes=unique(rows('routes.txt'),'route_id');trips=unique(rows('trips.txt'),'trip_id')
    calendars=list(rows('calendar.txt'));exceptions=list(rows('calendar_dates.txt'));feeds=list(rows('feed_info.txt'))
    unique(calendars,'service_id')
    if len(feeds)!=1:raise ValueError('Expected one explicit feed date range')
    info=feeds[0];start=info['feed_start_date'];end=info['feed_end_date']
    if not re.fullmatch(r'\d{8}',start+'' ) or not re.fullmatch(r'\d{8}',end) or start>end:raise ValueError('Invalid feed dates')
    for r in calendars:
        for key in ('start_date','end_date'):datetime.strptime(r[key],'%Y%m%d')
        if r['start_date']>r['end_date'] or any(r[key] not in ('0','1') for key in ('monday','tuesday','wednesday','thursday','friday','saturday','sunday')):raise ValueError('Invalid service calendar')
    for r in exceptions:datetime.strptime(r['date'],'%Y%m%d')
    services={r['service_id'] for r in calendars+exceptions}
    for r in trips.values():
        if r['route_id'] not in routes or r['service_id'] not in services:raise ValueError('Unresolved trip reference')
    for r in exceptions:
        if r['exception_type'] not in ('1','2'):raise ValueError('Invalid service exception')
    if len({(r['service_id'],r['date']) for r in exceptions})!=len(exceptions):raise ValueError('Duplicate service exception')
    project=Transformer.from_crs(4326,26917,always_xy=True)
    output_stops={};stop_routes=defaultdict(set);counts=Counter();seen=defaultdict(set);events=defaultdict(Counter)
    for id,r in stops.items():
        if r['parent_station'] and r['parent_station'] not in stops:raise ValueError('Missing parent station')
        xy=None
        if r.get('location_type','0') in ('','0'):
            lon,lat=float(r['stop_lon']),float(r['stop_lat'])
            if not (-81<lon<-78 and 43<lat<45.5):raise ValueError('Stop outside validated coordinate envelope')
            xy=list(project.transform(lon,lat))
        output_stops[id]={'attributes':r,'xy':xy}
    for r in rows('stop_times.txt'):
        counts['stop_times']+=1
        trip=trips.get(r['trip_id']);stop=r['stop_id']
        if not trip or stop not in stops:raise ValueError('Unresolved stop-time reference')
        seq=int(r['stop_sequence'])
        if seq in seen[r['trip_id']]:raise ValueError('Duplicate trip/stop sequence')
        seen[r['trip_id']].add(seq);stop_routes[stop].add(trip['route_id'])
        if r.get('pickup_type','') not in ('','0','1','2','3'):raise ValueError('Invalid pickup type')
        if r.get('pickup_type','') not in ('','0'):
            counts['non_regular_pickup_rows']+=1;continue
        if not r['departure_time']:
            counts['missing_departure_rows']+=1;continue
        h=hour(r['departure_time']);events[stop][(trip['route_id'],trip['service_id'],h)]+=1;counts['counted_departure_rows']+=1
    if set(seen)!=set(trips):raise ValueError('Trips without stop times')
    for id,r in output_stops.items():
        r['routes']=sorted(stop_routes[id]);r['hours']=[[*key,value] for key,value in sorted(events[id].items())]
    payload={'stops':output_stops,'routes':routes,'calendar':calendars,'exceptions':exceptions}
    raw=encoded(payload);object_id=hashlib.sha256(raw).hexdigest()
    identity={'archive':digest,'builder':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'object':object_id}
    snapshot_id=hashlib.sha256(encoded(identity)).hexdigest()[:20]
    manifest={'id':snapshot_id,'object':object_id,'source':receipt,'agency':agencies,'feed':info,
              'counts':{**counts,'stops':len(stops),'boarding_stops':sum(r['xy'] is not None for r in output_stops.values()),'routes':len(routes),'trips':len(trips)},
              'method':'Straight-line stop proximity in EPSG:26917. Hourly counts of published regular-pickup stop-time rows, including after-midnight service-day times. Supplied intermediate times are retained; missing times are not interpolated.',
              'limitations':['TTC only; other operators are not integrated.','Scheduled counts are not real-time arrivals, observed reliability, walking access or a guarantee of accessibility.','Counts at neighbouring stops may include the same trip; do not sum them as unique vehicles.','Stops and route associations describe the feed period; hourly counts apply to the selected date and local hour.']}
    output.mkdir(parents=True,exist_ok=True);(output/'objects').mkdir(exist_ok=True)
    obj=output/'objects'/f'{object_id}.json.gz'
    if not obj.exists():obj.write_bytes(gzip.compress(raw,mtime=0))
    target=output/snapshot_id;target.mkdir(exist_ok=True)
    if not (target/'manifest.json').exists():(target/'manifest.json').write_bytes(encoded(manifest))
    tmp=output/'latest.tmp';tmp.write_bytes(encoded({'id':snapshot_id}));tmp.replace(output/'latest.json')
    return manifest

def package_transport(source:Path,destination:Path):
    if not (source/'latest.json').exists():return {'available':False}
    total=0;ids=set()
    for path in source.glob('*/manifest.json'):
        m=json.loads(path.read_text());id=m['id'];digest=m['object']
        if not re.fullmatch('[a-f0-9]{20}',id) or id!=path.parent.name or not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Invalid transport snapshot')
        obj=source/'objects'/f'{digest}.json.gz'
        if hashlib.sha256(gzip.decompress(obj.read_bytes())).hexdigest()!=digest:raise ValueError('Transport checksum mismatch')
        (destination/id).mkdir(parents=True,exist_ok=True);(destination/'objects').mkdir(exist_ok=True)
        shutil.copy2(path,destination/id/'manifest.json');shutil.copy2(obj,destination/'objects'/obj.name);total+=path.stat().st_size+obj.stat().st_size;ids.add(id)
    latest=json.loads((source/'latest.json').read_text())
    if latest['id'] not in ids:raise ValueError('Missing transport latest snapshot')
    if total>5_000_000:raise ValueError('Transport package exceeds 5 MB budget')
    shutil.copy2(source/'latest.json',destination/'latest.json')
    return {'available':True,'snapshots':sorted(ids),'bytes':total}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=ROOT/'data/transport-source');p.add_argument('--output',type=Path,default=ROOT/'public/transport');a=p.parse_args();print(json.dumps(build(a.source,a.output),ensure_ascii=False))
