import {useEffect,useRef,useState} from 'react';
import * as maplibregl from 'maplibre-gl';
import type {FeatureCollection,Feature,Geometry} from 'geojson';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import type {Neighbourhood,PlanningDataProvider,PlanningFeature,PlanningQuery} from './types';
maplibregl.setWorkerUrl(workerUrl);
const empty:FeatureCollection={type:'FeatureCollection',features:[]};
export function PlanningMap({provider,neighbourhoods,query,rows,threeD,onLocation,onInspect}:{provider:PlanningDataProvider;neighbourhoods:Neighbourhood[];query:PlanningQuery;rows:PlanningFeature[];threeD:boolean;onLocation:(lon:number,lat:number)=>void;onInspect:(f:PlanningFeature)=>void}){
 const container=useRef<HTMLDivElement>(null),map=useRef<maplibregl.Map|null>(null),callbacks=useRef({onLocation,onInspect,rows});callbacks.current={onLocation,onInspect,rows};
 const [ready,setReady]=useState(false),[error,setError]=useState(''),[buildingNote,setBuildingNote]=useState('');
 useEffect(()=>{
  if(!container.current)return;let m:maplibregl.Map;
  try{m=new maplibregl.Map({container:container.current,center:[query.lon,query.lat],zoom:13.5,attributionControl:false,style:{version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#e6eeeb'}}]}});}catch{setError('Map unavailable. Address search, neighbourhood selection and the complete results list remain available.');return;}
  map.current=m;m.addControl(new maplibregl.NavigationControl(),'top-right');m.addControl(new maplibregl.ScaleControl({unit:'metric'}));m.addControl(new maplibregl.AttributionControl({compact:false,customAttribution:'Contains information licensed under the Open Government Licence – Toronto'}));
  m.on('load',()=>{
   m.addSource('areas',{type:'geojson',data:{type:'FeatureCollection',features:neighbourhoods.map(n=>({type:'Feature',geometry:n.geometry,properties:{name:n.label}}))}});
   m.addLayer({id:'areas-fill',type:'fill',source:'areas',paint:{'fill-color':'#f5f5ed','fill-opacity':.8}});
   m.addLayer({id:'areas-line',type:'line',source:'areas',paint:{'line-color':'#c3cec6','line-width':1}});
   for(const id of ['context','buildings','radius','results','centre'])m.addSource(id,{type:'geojson',data:empty});
   m.addLayer({id:'context',type:'line',source:'context',paint:{'line-color':'#ffffff','line-width':['interpolate',['linear'],['zoom'],10,.5,16,3]}});
   m.addLayer({id:'buildings',type:'fill-extrusion',source:'buildings',paint:{'fill-extrusion-color':'#a4b8b3','fill-extrusion-height':['get','height'],'fill-extrusion-opacity':.7}});
   m.addLayer({id:'radius-fill',type:'fill',source:'radius',paint:{'fill-color':'#087f78','fill-opacity':.06}});
   m.addLayer({id:'radius-line',type:'line',source:'radius',paint:{'line-color':'#087f78','line-width':2,'line-dasharray':[3,2]}});
   m.addLayer({id:'result-fill',type:'fill',source:'results',filter:['==',['geometry-type'],'Polygon'],paint:{'fill-color':'#c47b25','fill-opacity':.25}});
   m.addLayer({id:'result-line',type:'line',source:'results',filter:['==',['geometry-type'],'Polygon'],paint:{'line-color':'#8b561d','line-width':1.5}});
   m.addLayer({id:'result-points',type:'circle',source:'results',filter:['==',['geometry-type'],'Point'],paint:{'circle-radius':7,'circle-color':['match',['get','status'],'Under Review','#b2731c','Active','#167d88','Built','#675a9b','#51646a'],'circle-stroke-color':'#fff','circle-stroke-width':2}});
   m.addLayer({id:'centre',type:'circle',source:'centre',paint:{'circle-radius':5,'circle-color':'#162e33','circle-stroke-width':3,'circle-stroke-color':'#fff'}});
   setReady(true);provider.context().then(data=>{if(map.current===m)(m.getSource('context') as maplibregl.GeoJSONSource)?.setData(data);}).catch(()=>setError('Street reference unavailable; planning results remain available.'));
  });
  m.on('click',e=>{const found=m.queryRenderedFeatures(e.point,{layers:['result-points','result-fill'].filter(id=>!!m.getLayer(id))})[0];const row=callbacks.current.rows.find(r=>r.id===found?.properties?.id);if(row)callbacks.current.onInspect(row);else callbacks.current.onLocation(e.lngLat.lng,e.lngLat.lat);});
  const observer=new ResizeObserver(()=>m.resize());observer.observe(container.current);
  return()=>{observer.disconnect();map.current=null;m.remove();};
 },[provider]);
 useEffect(()=>{const m=map.current;if(!ready||!m)return;const coords:number[][]=[];for(let i=0;i<=96;i++){const a=2*Math.PI*i/96;coords.push([query.lon+Math.cos(a)*query.radius/(111320*Math.cos(query.lat*Math.PI/180)),query.lat+Math.sin(a)*query.radius/111320]);}
  (m.getSource('radius') as maplibregl.GeoJSONSource).setData({type:'Feature',geometry:{type:'Polygon',coordinates:[coords]},properties:{}});
  (m.getSource('centre') as maplibregl.GeoJSONSource).setData({type:'Feature',geometry:{type:'Point',coordinates:[query.lon,query.lat]},properties:{}});
  m.easeTo({center:[query.lon,query.lat],zoom:query.radius===400?15:query.radius===800?14.2:13.2,duration:window.matchMedia('(prefers-reduced-motion: reduce)').matches?0:500});
 },[ready,query.lon,query.lat,query.radius]);
 useEffect(()=>{const m=map.current;if(!ready||!m)return;const features:Feature[]=[];for(const r of rows){const geometry:Geometry|null=r.geometry||(r.lon!=null&&r.lat!=null?{type:'Point',coordinates:[r.lon,r.lat]}:null);if(geometry)features.push({type:'Feature',geometry,properties:{id:r.id,status:r.status}});}(m.getSource('results') as maplibregl.GeoJSONSource).setData({type:'FeatureCollection',features});},[ready,rows]);
 useEffect(()=>{const m=map.current;if(!ready||!m)return;let cancelled=false;m.easeTo({pitch:threeD?48:0,duration:0});(m.getSource('buildings') as maplibregl.GeoJSONSource).setData(empty);
  if(threeD){setBuildingNote('Loading nearby building context…');provider.buildings(query.lon,query.lat).then(data=>{if(!cancelled){(m.getSource('buildings') as maplibregl.GeoJSONSource).setData(data);setBuildingNote(`${data.features.length.toLocaleString()} component footprints in nearby tiles · illustrative height · flat base`);}}).catch(()=>{if(!cancelled)setBuildingNote('Building context unavailable.');});}else setBuildingNote('');return()=>{cancelled=true;};
 },[ready,threeD,query.lon,query.lat,provider]);
 return <section className="planning-map" aria-label="Development map"><div ref={container} className="planning-map-canvas"/><div className="map-caption">TORONTO / OFFICIAL REFERENCE DATA<span>Click the map to choose a location</span></div>{error&&<p role="status" className="map-notice">{error}</p>}{buildingNote&&<p className="building-note">{buildingNote}</p>}<div className="map-legend">{query.kind==='projects'?<><span><i style={{background:'#b2731c'}}/>Under Review</span><span><i style={{background:'#167d88'}}/>Active</span><span><i style={{background:'#675a9b'}}/>Built</span><small>Publisher statuses · not a construction forecast</small></>:<><span><i style={{background:query.kind==='applications'?'#51646a':'#c47b25'}}/>{query.kind==='applications'?'Application source points':'Mapped zoning polygons'}</span><small>{query.kind==='applications'?'Inspect each record for its publisher status':'Reference only · check amendments and exceptions'}</small></>}</div></section>;
}
