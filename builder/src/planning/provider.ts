import type {PlanningDataProvider,PlanningFeature,PlanningQuery} from './types';
export function createProvider():PlanningDataProvider{
 const worker=new Worker(new URL('./worker.ts',import.meta.url),{type:'module'});let next=0;
 const pending=new Map<number,{resolve:(v:any)=>void;reject:(e:Error)=>void}>();
 worker.onmessage=({data})=>{const call=pending.get(data.id);pending.delete(data.id);if(data.error)call?.reject(new Error(data.error));else call?.resolve(data.result);};
 worker.onerror=()=>{pending.forEach(p=>p.reject(new Error('Planning worker failed. Reload to retry.')));pending.clear();};
 function call(type:string,args?:unknown):Promise<any>{return new Promise((resolve,reject)=>{const id=next++;pending.set(id,{resolve,reject});worker.postMessage({id,type,args});});}
 return {init:(id?:string)=>call('init',{id,base:new URL('planning/',new URL(import.meta.env.BASE_URL,document.baseURI)).href}),searchAddress:(query:string)=>call('search',query),query:(query:PlanningQuery)=>call('query',query),inspect:(feature:PlanningFeature)=>call('inspect',feature),context:()=>call('context'),buildings:(lon:number,lat:number)=>call('buildings',{lon,lat}),close:()=>{worker.terminate();pending.forEach(p=>p.reject(new Error('Explorer closed')));pending.clear();}};
}
