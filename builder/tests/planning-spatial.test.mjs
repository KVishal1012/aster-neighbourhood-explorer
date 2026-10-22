import test from 'node:test';
import assert from 'node:assert/strict';
import {project,geometryDistance,validateQuery,cellKeys} from '../src/planning/spatial.ts';
test('projection agrees with pyproj EPSG:26917 controls within 2 cm',()=>{
 for(const [lon,lat,x,y] of [[-79.3832,43.6532,630378.9952621169,4834625.70076407],[-79.64,43.85,609311.5492131322,4856111.736018137],[-79.12,43.6,651737.6392038295,4829164.354574866]]){
  const p=project(lon,lat);assert.ok(Math.hypot(p[0]-x,p[1]-y)<.02);
 }
});
test('polygon holes and exact radius edges are respected',()=>{
 const g={type:'Polygon',coordinates:[[[0,0],[100,0],[100,100],[0,100],[0,0]],[[40,40],[60,40],[60,60],[40,60],[40,40]]]};
 assert.equal(geometryDistance([20,20],g),0);assert.equal(geometryDistance([50,50],g),10);
 assert.equal(geometryDistance([-400,0],g),400);assert.ok(geometryDistance([-400.01,0],g)>400);
});
test('multipolygon and cell crossing',()=>{
 assert.equal(geometryDistance([0,0],{type:'MultiPolygon',coordinates:[[[[10,0],[20,0],[20,10],[10,0]]]]}),10);
 assert.equal(cellKeys([2000,2000],1).length,4);
});
test('invalid query never becomes a citywide scan',()=>{
 for(const q of [{lon:NaN,lat:43.6,radius:800,kind:'projects'},{lon:-79.4,lat:43.6,radius:99999,kind:'projects'},{lon:-79.4,lat:43.6,radius:800,kind:'secret'}])assert.throws(()=>validateQuery(q));
});
