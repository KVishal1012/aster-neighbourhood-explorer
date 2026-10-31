"""Archive two stable reads of the official TTC merged GTFS and its explicit licence.

Creates a new dated acquisition directory; existing acquisition evidence is retained.
Run build_transport.py --source <returned directory> after successful acquisition.
"""
from datetime import datetime,timezone
import hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CATALOGUE='https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show?id=merged-gtfs-ttc-routes-and-schedules'
PAGE='https://open.toronto.ca/dataset/merged-gtfs-ttc-routes-and-schedules/'
LICENCE='https://open.toronto.ca/open-data-licence/'
FEED='https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/b811ead4-6eaf-4adb-8408-d389fb5a069c/resource/c920e221-7a1c-488b-8c5b-6d8cd4e85eaf/download/completegtfs.zip'

def acquire():
    now=datetime.now(timezone.utc);folder=ROOT/'data/transport-source'/now.strftime('%Y%m%dT%H%M%S%fZ');folder.mkdir(parents=True)
    def get(url,name):
        subprocess.run(['curl','--fail','--silent','--show-error','--location','--proto','=https','--proto-redir','=https','--max-time','180',url,'--output',str(folder/name)],check=True)
    get(CATALOGUE,'catalogue.json');get(PAGE,'dataset-page.html');get(LICENCE,'licence.html')
    initial=json.loads((folder/'catalogue.json').read_text())['result']
    resources=[r for r in initial['resources'] if r['url']==FEED]
    if len(resources)!=1 or initial['license_id']!='notspecified':raise ValueError('Source contract changed; review catalogue and licence')
    if LICENCE not in (folder/'dataset-page.html').read_text() or 'Open Government Licence' not in (folder/'licence.html').read_text():raise ValueError('Explicit licence evidence missing')
    get(FEED,'merged.zip');get(FEED,'merged-repeat.zip');get(CATALOGUE,'catalogue-final.json')
    final=json.loads((folder/'catalogue-final.json').read_text())['result']
    sha=lambda name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
    if sha('merged.zip')!=sha('merged-repeat.zip') or initial['resources']!=final['resources']:raise ValueError('Feed changed during acquisition; snapshot not qualified')
    receipt={'retrieved_at':datetime.now(timezone.utc).isoformat(),'source_url':FEED,'source_modified_at':resources[0]['last_modified'],'page':PAGE,'licence_url':LICENCE,'api_licence':initial['license_id'],'licence_basis':'Official dataset page explicitly links Open Government Licence – Toronto. API licence field is not specified.','sha256':sha('merged.zip'),'evidence':{name:sha(name) for name in ('catalogue.json','catalogue-final.json','licence.html','dataset-page.html')},'stable_reread':True}
    (folder/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return folder

if __name__=='__main__':print(acquire())
