import {decodeJsonResponse} from './decode';
import type {Address,Neighbourhood,PlanningSnapshot,PlanningFeature,PlanningQuery,Municipality,MunicipalityInfo} from './types';
import {project,geometryDistance,cellKeys,validateQuery,containsDisk} from './spatial';
let root='', baseRoot='', snapshot:PlanningSnapshot,neighbourhoods:Neighbourhood[]=[];
let municipalities:Municipality[]=[];
let catalogs:Record<string,string>={},municipalityInfo:MunicipalityInfo[]=[];
let complete=false, fullTask:Promise<void>|null=null;
async function ensureSnapshot(){
 if(complete)return;
 if(!fullTask)fullTask=(async()=>{const full=await read('manifest.json');if(full.id!==snapshot.id)throw new Error('Snapshot identity mismatch');snapshot=full;complete=true;})().finally(()=>{fullTask=null;});
 await fullTask;
}
async function loadBoundaries(){
 await ensureSnapshot();
 [neighbourhoods,municipalities]=await Promise.all([read('neighbourhoods.json'),snapshot.regional?read('municipalities.json'):Promise.resolve([])]);
 municipalityInfo=municipalities;
 return {neighbourhoods,municipalities};
}
async function readObject(digest:string){
 if(!/^[a-f0-9]{64}$/.test(digest))throw new Error('Invalid search object identity');
 const key='object:'+digest;
 if(!cache.has(key))cache.set(key,fetch(baseRoot+'objects/'+digest+'.json.gz').then(r=>{if(!r.ok)throw new Error('Address index unavailable in the pinned snapshot. Retry your search.');return decodeJsonResponse(r);}).catch(e=>{cache.delete(key);throw e;}));
 if(cache.size>60)cache.delete(cache.keys().next().value!);
 return cache.get(key);
}
const cache=new Map<string,Promise<any>>();
async function read(path:string):Promise<any>{
 if(!cache.has(path)){
  const task=(async()=>{
   let r=await fetch(path==='manifest.json'?root+'manifest.json.gz':baseRoot+'objects/'+snapshot.assets[path]+'.json.gz');
   // Older deployments retain the same snapshot at its uncompressed URL.
   if(path==='manifest.json'&&(r.status===404||r.headers.get('content-type')?.includes('text/html')))r=await fetch(root+path);
   if(!r.ok)throw new Error(`Snapshot resource unavailable: ${path}. No newer snapshot was substituted.`);
   return decodeJsonResponse(r);
  })().catch(e=>{cache.delete(path);throw e;});
  cache.set(path,task);if(cache.size>60)cache.delete(cache.keys().next().value!);
 }
 return cache.get(path);
}
async function run(type:string,args:any):Promise<unknown>{
 if(type==='init'){
  const base=args.base as string;baseRoot=base;
  let health:any;try{const response=await fetch(base+'latest.json',{cache:'no-store'});if(!response.ok)throw new Error('No qualified planning snapshot is available.');health=await response.json();}catch(error){if(!args.id)throw error;health={status:'unavailable',checked_at:'',error:'Latest update health unavailable; displaying the requested historical snapshot.'};}
  const id=args.id||health.id;if(!/^[a-f0-9]{20}$/.test(id))throw new Error('Invalid snapshot identifier');
  root=base+id+'/';cache.clear();complete=false;fullTask=null;catalogs={};municipalities=[];neighbourhoods=[];municipalityInfo=[];
  if(args.lightweight){
   const response=await fetch(root+'startup-v1.json.gz');
   if(response.ok&&!response.headers.get('content-type')?.includes('text/html')){
    const startup=await decodeJsonResponse(response) as any;
    if(startup.version!==1||startup.snapshot.id!==id)throw new Error('Search startup identity mismatch');
    snapshot=startup.snapshot;catalogs=startup.catalogs;municipalityInfo=startup.municipalities;
    return {snapshot,neighbourhoods:startup.neighbourhoods,municipalities:municipalityInfo,health};
   }
   if(response.status!==404&&!response.headers.get('content-type')?.includes('text/html'))throw new Error('Search startup unavailable. Reload to retry the pinned snapshot.');
  }
  snapshot=await read('manifest.json');
  if(snapshot.id!==id)throw new Error('Snapshot identity mismatch');
  complete=true;await loadBoundaries();
  return {snapshot,neighbourhoods,municipalities,health};
 }
 if(!snapshot)throw new Error('Snapshot not initialized');
 if(type==='snapshot'){await ensureSnapshot();return snapshot;}
 if(type==='boundaries')return loadBoundaries();
 if(type==='search'){
  const query=String(typeof args==='string'?args:args.query).trim().toUpperCase().replace(/\s+/g,' ');if(query.length<3)return [];
  const areaId=args.jurisdiction_id||snapshot.sources.addresses.jurisdiction_id;
  if(catalogs[areaId]){
   const area=municipalityInfo.find(m=>m.id===areaId);
   if(!area?.layers.addresses?.length)throw new Error('Municipal address search is not integrated here.');
   const catalog=await readObject(catalogs[areaId]);let matches:Address[]=[];
   if(catalog.format==='matches'){
    const digest=catalog.buckets[query.slice(0,3)];if(!digest)return [];
    const rows=await readObject(digest);
    matches=rows.filter((r:Address)=>r.label.toUpperCase().replace(/\s+/g,' ').startsWith(query)||r.street.toUpperCase().replace(/\s+/g,' ').startsWith(query));
   }else{
    const field=/^\d/.test(query)?'search_label':'street';
    for(const shard of catalog[field].filter((d:any)=>d.max>=query&&d.min<=query+'\uffff')){
     matches.push(...(await readObject(shard.digest)).filter((r:any)=>r.jurisdiction_id===areaId&&String(r[field]).startsWith(query)));
     if(matches.length>=30)break;
    }
   }
   return matches.slice(0,30).map(r=>({...r,jurisdiction_id:areaId,municipality:area.name,source_key:r.source_key||snapshot.address_search?.[areaId].source_key,source_snapshot_id:r.source_snapshot_id||snapshot.source_snapshots?.toronto}));
  }
  if(municipalityInfo.length&&!municipalityInfo.find(m=>m.id===areaId)?.layers.addresses?.length)throw new Error('Municipal address search is not integrated here. Select a map location instead.');
  await loadBoundaries();
  if(municipalities.length){
   const area=municipalities.find(m=>m.id===(args.jurisdiction_id||snapshot.sources.addresses.jurisdiction_id));
   if(!area?.layers.addresses?.length)throw new Error('Municipal address search is not integrated here. Select a map location instead.');
   const routing=snapshot.address_search?.[area.id];
   if(routing){
    if(routing.format==='legacy-address-matches'){
     const directory:Record<string,string>=await read(routing.index),bucket=directory[query.slice(0,3)];
     if(!bucket)return [];
     const rows=await read(bucket);
     return rows.filter((r:Address)=>r.label.toUpperCase().replace(/\s+/g,' ').startsWith(query)||r.street.toUpperCase().replace(/\s+/g,' ').startsWith(query)).slice(0,30).map((r:Address)=>({...r,jurisdiction_id:area.id,municipality:area.name,source_key:'addresses',source_snapshot_id:snapshot.source_snapshots?.toronto}));
    }
    if(routing.format==='legacy-prefix'){
     const directory:Record<string,string>=await read(routing.index),bucket=directory[query.slice(0,3)];
     if(!bucket)return [];
     const index:Record<string,string[]>=await read(bucket),prefix=query.slice(0,routing.prefix_length||8);
     const paths=[...new Set(Object.entries(index).filter(([key])=>key.startsWith(prefix)).flatMap(([,paths])=>paths))].sort();
     const matches:Address[]=[];
     for(const path of paths){
      const rows:Address[]=await read(path);
      matches.push(...rows.filter(r=>r.label.toUpperCase().replace(/\s+/g,' ').startsWith(query)||r.street.toUpperCase().replace(/\s+/g,' ').startsWith(query)).map(r=>({...r,jurisdiction_id:area.id,municipality:area.name,source_key:'addresses',source_snapshot_id:snapshot.source_snapshots?.toronto})));
      if(matches.length>=30)break;
     }
     return matches.sort((a,b)=>a.label.localeCompare(b.label)||a.id.localeCompare(b.id)).slice(0,30);
    }
    const index=await read(routing.index);const field=/^\d/.test(query)?'search_label':'street';
    const upper=query+'\uffff';const shards=index[field].filter((d:{min:string;max:string})=>d.max>=query&&d.min<=upper);
    const matches:Address[]=[];
    for(const shard of shards){
     const rows=await read(shard.path);
     matches.push(...rows.filter((r:any)=>r.jurisdiction_id===area.id&&String(r[field]).startsWith(query)).map((r:Address)=>({...r,municipality:area.name})));
     if(matches.length>=30)break;
    }
    return matches.slice(0,30);
   }
   if(area.id!==snapshot.sources.addresses.jurisdiction_id)throw new Error('Address index unavailable in the pinned snapshot.');
  }
  const names:[string,string][]=await read('streets-search.json');const streetQuery=query.replace(/^\d+[A-Z]?\s*/, '');
  if(!streetQuery)return [];
  const keys=[...new Set(names.filter(([name])=>name.startsWith(streetQuery)).map(([,key])=>key))];
  const rows:Address[]=(await Promise.all(keys.map(k=>read(`addresses/${k}.json`)))).flat();
  return rows.filter(r=>r.label.toUpperCase().startsWith(query)||r.street.startsWith(query)).sort((a,b)=>a.label.localeCompare(b.label)).slice(0,30);
 }
 await ensureSnapshot();
 if(type==='inspect'&&args.address_shard){const full=(await read(args.address_shard)).find((r:Address)=>r.id===args.id);if(!full||full.label!==args.label)throw new Error('Address evidence missing from pinned snapshot');return {...args,...full};}
 if(type==='inspect'){const full=args.detail?(await read(args.detail))[args.id]:args;if(!full)throw new Error('Evidence record missing from pinned snapshot');return {...args,...full};}
 if(type==='context')return read('context.json');
 if(type==='buildings'){
  const p=project(args.lon,args.lat), keys=cellKeys(p,1000).filter(k=>snapshot.tiles.buildings?.includes(k));
  const rows=(await Promise.all(keys.map(k=>read(`buildings/${k}.json`)))).flat();
  return {type:'FeatureCollection',features:[...new Map(rows.map(r=>[r.id,r])).values()]};
 }
 if(type==='query'){
  const q=args as PlanningQuery;validateQuery(q);await loadBoundaries();const p=project(q.lon,q.lat);
  if(snapshot.regional){
   const touched=municipalities.filter(m=>geometryDistance(p,m.metric)<=q.radius);
   const integrated=(m:Municipality)=>q.source_key?!!m.layers[q.kind]?.includes(q.source_key):!!m.layers[q.kind]?.length;
   const coverage_notes=touched.filter(m=>!integrated(m)).map(m=>`${m.name}: ${q.source_key||q.kind} not integrated. ${m.qualification_layers?.[q.kind]?.reason||m.coverage_note}`);
   touched.filter(integrated).forEach(m=>coverage_notes.push(`${m.name}: ${m.layers[q.kind].filter(k=>!q.source_key||k===q.source_key).map(k=>snapshot.sources[k]?.notes||m.coverage_note).join(' ')}`));
   if(!containsDisk(p,q.radius,await read('gta-coverage.json')))coverage_notes.push('The search circle extends outside qualified GTA municipal boundaries; those portions are not covered.');
   let rows:PlanningFeature[]=[];
   if(q.unlocated&&(['projects','applications','regional_reviews'].includes(q.kind)))rows=snapshot.assets[`unlocated/${q.kind}.json`]?await read(`unlocated/${q.kind}.json`):[];
   else if(!q.unlocated){const keys=cellKeys(p,q.radius).filter(k=>snapshot.tiles[q.kind]?.includes(k));rows=[...new Map<string,PlanningFeature>((await Promise.all(keys.map(k=>read(`${q.kind}/${k}.json`)))).flat().map(r=>[r.id,r])).values()];}
   rows=rows.filter(r=>!q.source_key||(r.source_key||r.kind)===q.source_key)
    .filter(r=>!q.stage||(q.source_key?r.original_status||'Not supplied':r.status)===q.stage)
    .filter(r=>!q.text||`${r.label} ${r.number||''}`.toLowerCase().includes(q.text.toLowerCase()));
   if(q.unlocated)rows=rows.filter(r=>r.jurisdiction_id===(q.jurisdiction_id||snapshot.sources.applications.jurisdiction_id)||(!r.jurisdiction_id&&!!q.source_key));
   else rows=rows.flatMap(r=>{const distance=r.metric?geometryDistance(p,r.metric):r.xy?Math.hypot(p[0]-r.xy[0],p[1]-r.xy[1]):Infinity;return distance<=q.radius?[{...r,distance}]:[];});
   rows.sort((a,b)=>(a.distance??Infinity)-(b.distance??Infinity)||a.id.localeCompare(b.id));
   return {snapshot_id:snapshot.id,query:q,rows,coverage:touched.some(integrated),coverage_notes,jurisdictions:touched.map(m=>m.id),method:snapshot.method};
  }
  const coverage=snapshot.assets['coverage.json']?geometryDistance(p,await read('coverage.json'))===0:neighbourhoods.some(n=>n.metric&&geometryDistance(p,n.metric)===0);
  let rows:PlanningFeature[]=[];
  if(['projects','applications','regional_reviews'].includes(q.kind))rows=await read(`${q.kind}.json`);
  else if(coverage&&!q.unlocated){
   const keys=cellKeys(p,q.radius).filter(k=>snapshot.tiles[q.kind]?.includes(k));
   rows=[...new Map<string,PlanningFeature>((await Promise.all(keys.map(k=>read(`${q.kind}/${k}.json`)))).flat().map(r=>[r.id,r])).values()];
  }
  rows=rows.filter(r=>!q.stage||r.status===q.stage).filter(r=>!q.text||`${r.label} ${r.number||''}`.toLowerCase().includes(q.text.toLowerCase()));
  if(q.unlocated)rows=rows.filter(r=>r.geometry_origin==='unlocated');
  else if(!coverage)rows=[];
  else rows=rows.flatMap(r=>{const distance=r.metric?geometryDistance(p,r.metric):r.xy?Math.hypot(p[0]-r.xy[0],p[1]-r.xy[1]):Infinity;return distance<=q.radius?[{...r,distance}]:[];});
  rows.sort((a,b)=>(a.distance??Infinity)-(b.distance??Infinity)||a.id.localeCompare(b.id));
  return {snapshot_id:snapshot.id,query:q,rows,coverage,method:snapshot.method};
 }
 throw new Error('Unknown planning operation');
}
self.onmessage=async(event:MessageEvent)=>{const {id,type,args}=event.data;try{self.postMessage({id,result:await run(type,args)});}catch(error){self.postMessage({id,error:error instanceof Error?error.message:String(error)});}};
