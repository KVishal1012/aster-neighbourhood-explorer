import {project} from './spatial.ts';
export type TransitStop={attributes:Record<string,string>;xy:[number,number]|null;routes:string[];hours:[string,string,number,number][]};
export type TransitData={stops:Record<string,TransitStop>;routes:Record<string,Record<string,string>>;calendar:Record<string,string>[];exceptions:Record<string,string>[]};
export type TransitManifest={id:string;object:string;source:{page:string;licence_url:string;retrieved_at:string;source_modified_at:string;sha256:string;api_licence:string;licence_basis:string};feed:{feed_start_date:string;feed_end_date:string;feed_version:string};counts:Record<string,number>;method:string;limitations:string[]};
export function dateKey(date:string){
 const parsed=new Date(date+'T12:00:00Z');
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Number.isFinite(parsed.valueOf())||parsed.toISOString().slice(0,10)!==date)throw new Error('Choose a valid date.');
 return date.replaceAll('-','');
}
export function activeServices(data:TransitData,date:string){
 const key=dateKey(date),day=['sunday','monday','tuesday','wednesday','thursday','friday','saturday'][new Date(date+'T12:00:00Z').getUTCDay()];
 const ids=new Set(data.calendar.filter(r=>r.start_date<=key&&key<=r.end_date&&r[day]==='1').map(r=>r.service_id));
 data.exceptions.filter(r=>r.date===key).forEach(r=>r.exception_type==='1'?ids.add(r.service_id):ids.delete(r.service_id));return ids;
}
export function nearbyTransit(data:TransitData,manifest:TransitManifest,lon:number,lat:number,radius:number,date:string,hour:number){
 if(![400,800,1600].includes(radius)||!Number.isInteger(hour)||hour<0||hour>23)throw new Error('Choose a supported radius and hour.');
 const key=dateKey(date),coveredDate=key>=manifest.feed.feed_start_date&&key<=manifest.feed.feed_end_date;
 const point=project(lon,lat),days=[0,1,2].map(offset=>{const d=new Date(date+'T12:00:00Z');d.setUTCDate(d.getUTCDate()-offset);return activeServices(data,d.toISOString().slice(0,10));});
 const rows=Object.entries(data.stops).flatMap(([id,stop])=>{
  if(!stop.xy)return [];const distance=Math.hypot(stop.xy[0]-point[0],stop.xy[1]-point[1]);if(distance>radius)return [];
  const departures:Record<string,number>={};
  if(coveredDate)for(const [route,service,h,count] of stop.hours){const offset=Math.floor(h/24);if(h%24===hour&&days[offset]?.has(service))departures[route]=(departures[route]||0)+count;}
  return [{id,attributes:stop.attributes,distance,routes:stop.routes.map(id=>({id,...data.routes[id],route_short_name:data.routes[id].route_short_name,route_long_name:data.routes[id].route_long_name,departures:coveredDate?(departures[id]||0):null}))}];
 }).sort((a,b)=>a.distance-b.distance||a.id.localeCompare(b.id));
 return {coveredDate,rows};
}
