import type {Address,Neighbourhood,PlanningSnapshot,PlanningFeature,PlanningQuery} from './types';
import {project,geometryDistance,cellKeys,validateQuery} from './spatial';
let root='', baseRoot='', snapshot:PlanningSnapshot,neighbourhoods:Neighbourhood[]=[];
const cache=new Map<string,Promise<any>>();
async function read(path:string):Promise<any>{
 if(!cache.has(path)){
  const task=fetch(path==='manifest.json'?root+path:baseRoot+'objects/'+snapshot.assets[path]+'.json.gz').then(async r=>{if(!r.ok)throw new Error(`Snapshot resource unavailable: ${path}. No newer snapshot was substituted.`);if(path==='manifest.json')return r.json();if(!r.body)throw new Error('Empty response');return JSON.parse(await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text());}).catch(e=>{cache.delete(path);throw e;});
  cache.set(path,task);if(cache.size>60)cache.delete(cache.keys().next().value!);
 }
 return cache.get(path);
}
async function run(type:string,args:any):Promise<unknown>{
 if(type==='init'){
  const base=args.base as string;baseRoot=base;
  let health:any;try{const response=await fetch(base+'latest.json',{cache:'no-store'});if(!response.ok)throw new Error('No qualified planning snapshot is available.');health=await response.json();}catch(error){if(!args.id)throw error;health={status:'unavailable',checked_at:'',error:'Latest update health unavailable; displaying the requested historical snapshot.'};}
  const id=args.id||health.id;if(!/^[a-f0-9]{20}$/.test(id))throw new Error('Invalid snapshot identifier');
  root=base+id+'/';cache.clear();snapshot=await read('manifest.json');neighbourhoods=await read('neighbourhoods.json');
  if(snapshot.id!==id)throw new Error('Snapshot identity mismatch');
  return {snapshot,neighbourhoods,health};
 }
 if(!snapshot)throw new Error('Snapshot not initialized');
 if(type==='search'){
  const query=String(args).trim().toUpperCase().replace(/\s+/g,' ');if(query.length<3)return [];
  const names:[string,string][]=await read('streets-search.json');const streetQuery=query.replace(/^\d+[A-Z]?\s*/, '');
  if(!streetQuery)return [];
  const keys=[...new Set(names.filter(([name])=>name.startsWith(streetQuery)).map(([,key])=>key))];
  const rows:Address[]=(await Promise.all(keys.map(k=>read(`addresses/${k}.json`)))).flat();
  return rows.filter(r=>r.label.toUpperCase().startsWith(query)||r.street.startsWith(query)).sort((a,b)=>a.label.localeCompare(b.label)).slice(0,30);
 }
 if(type==='inspect')return args.detail?(await read(args.detail))[args.id]:args;
 if(type==='context')return read('context.json');
 if(type==='buildings'){
  const p=project(args.lon,args.lat), keys=cellKeys(p,1000).filter(k=>snapshot.tiles.buildings?.includes(k));
  const rows=(await Promise.all(keys.map(k=>read(`buildings/${k}.json`)))).flat();
  return {type:'FeatureCollection',features:[...new Map(rows.map(r=>[r.id,r])).values()]};
 }
 if(type==='query'){
  const q=args as PlanningQuery;validateQuery(q);const p=project(q.lon,q.lat);
  const coverage=snapshot.assets['coverage.json']?geometryDistance(p,await read('coverage.json'))===0:neighbourhoods.some(n=>n.metric&&geometryDistance(p,n.metric)===0);
  let rows:PlanningFeature[]=[];
  if(q.kind==='projects'||q.kind==='applications')rows=await read(`${q.kind}.json`);
  else if(coverage&&!q.unlocated){
   const keys=cellKeys(p,q.radius).filter(k=>snapshot.tiles[q.kind].includes(k));
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
