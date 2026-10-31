import test from 'node:test';
import assert from 'node:assert/strict';
import {readdirSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {gzipSync} from 'node:zlib';
import {project} from '../src/planning/spatial.ts';

test('compiled public worker: no API dependency, pinned failures, unknown locations and exact radius',async()=>{
 const files=readdirSync('dist-public/assets');const worker=files.find(f=>/^worker-.*\.js$/.test(f));assert.ok(worker);
 const id='a'.repeat(20),p=project(-79.3832,43.6532);let response;
 const manifest={id,method:'EPSG:26917',tiles:{zoning:[],heights:[]},assets:{'neighbourhoods.json':'areas','projects.json':'projects'}};
 const neighbourhoods=[{metric:{type:'Polygon',coordinates:[[[p[0]-2000,p[1]-2000],[p[0]+2000,p[1]-2000],[p[0]+2000,p[1]+2000],[p[0]-2000,p[1]+2000],[p[0]-2000,p[1]-2000]]]}}];
 const rows=[{id:'projects:1',label:'Edge',status:'Active',geometry_origin:'address-derived point',xy:[p[0]+800,p[1]]},{id:'projects:2',label:'Outside',status:'Built',geometry_origin:'address-derived point',xy:[p[0]+800.01,p[1]]},{id:'projects:3',label:'Unlocated',status:'Active',geometry_origin:'unlocated',xy:null}];
 const originalFetch=globalThis.fetch;
 globalThis.self={postMessage:v=>response=v};
 globalThis.fetch=async url=>{
  assert.ok(!String(url).includes('/api/'));
  if(String(url).endsWith('latest.json'))return new Response('offline',{status:503});
  if(String(url).endsWith(id+'/manifest.json'))return Response.json(manifest);
  if(String(url).endsWith('/objects/areas.json.gz'))return new Response(gzipSync(JSON.stringify(neighbourhoods)));
  if(String(url).endsWith('/objects/projects.json.gz'))return new Response(gzipSync(JSON.stringify(rows)));
  return new Response('missing',{status:404});
 };
 try{
  await import(pathToFileURL(process.cwd()+'/dist-public/assets/'+worker));
  const call=async(type,args)=>{await self.onmessage({data:{id:1,type,args}});return response;};
  let r=await call('init',{base:'https://example.test/planning/',id});assert.equal(r.result.health.status,'unavailable');
  r=await call('query',{lon:-79.3832,lat:43.6532,radius:800,kind:'projects',stage:''});assert.equal(r.result.rows.length,1);assert.equal(r.result.rows[0].status,'Active');
  r=await call('query',{lon:-79.3832,lat:43.6532,radius:800,kind:'projects',stage:'',unlocated:true});assert.equal(r.result.rows[0].id,'projects:3');
  r=await call('search',{query:'AB'});assert.deepEqual(r.result,[]);
  r=await call('init',{base:'https://example.test/planning/',id:'b'.repeat(20)});assert.match(r.error,/No newer snapshot was substituted/);
 }finally{globalThis.fetch=originalFetch;delete globalThis.self;}
});
