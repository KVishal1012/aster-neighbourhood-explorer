/** WGS84 longitude/latitude to NAD83 UTM17 metre coordinates.
 * GRS80 ellipsoid with null horizontal datum shift: consistent with pyproj's
 * default Toronto WGS84->NAD83 operation. Tested against pyproj control points.
 */
export function project(lon:number,lat:number):[number,number]{
 if(!Number.isFinite(lon)||!Number.isFinite(lat)||lon < -80||lon > -78||lat < 43||lat > 45)throw new Error('Location is outside the supported Toronto-region envelope.');
 const a=6378137,f=1/298.257222101,e=f*(2-f),ep=e/(1-e),k=.9996;
 const p=lat*Math.PI/180,l=(lon+81)*Math.PI/180,s=Math.sin(p),c=Math.cos(p),t=Math.tan(p)**2,C=ep*c*c,A=c*l,N=a/Math.sqrt(1-e*s*s);
 const M=a*((1-e/4-3*e**2/64-5*e**3/256)*p-(3*e/8+3*e**2/32+45*e**3/1024)*Math.sin(2*p)+(15*e**2/256+45*e**3/1024)*Math.sin(4*p)-35*e**3/3072*Math.sin(6*p));
 return [500000+k*N*(A+(1-t+C)*A**3/6+(5-18*t+t*t+72*C-58*ep)*A**5/120),k*(M+N*Math.tan(p)*(A*A/2+(5-t+9*C+4*C*C)*A**4/24+(61-58*t+t*t+600*C-330*ep)*A**6/720))];
}
export type XY=number[];
export function segmentDistance(p:XY,a:XY,b:XY):number{
 const dx=b[0]-a[0],dy=b[1]-a[1],len=dx*dx+dy*dy;
 const t=len?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/len)):0;
 return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);
}
export function inRing(p:XY,ring:XY[]):boolean{
 let inside=false;
 for(let i=0,j=ring.length-1;i<ring.length;j=i++){
  const a=ring[i],b=ring[j];if(segmentDistance(p,a,b)<1e-7)return true;
  if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
 }
 return inside;
}
export function polygonDistance(p:XY,rings:XY[][]):number{
 if(inRing(p,rings[0])&&!rings.slice(1).some(r=>inRing(p,r)))return 0;
 let distance=Infinity;for(const r of rings)for(let i=1;i<r.length;i++)distance=Math.min(distance,segmentDistance(p,r[i-1],r[i]));
 return distance;
}
export function geometryDistance(p:XY,g:{type:string;coordinates?:unknown}):number{
 if(g.type==='Polygon')return polygonDistance(p,g.coordinates as XY[][]);
 if(g.type==='MultiPolygon')return Math.min(...(g.coordinates as XY[][][]).map(r=>polygonDistance(p,r)));
 if(g.type==='Point')return Math.hypot(p[0]-(g.coordinates as XY)[0],p[1]-(g.coordinates as XY)[1]);
 throw new Error('Unsupported analysis geometry');
}
export function cellKeys(p:XY,radius:number,size=2000):string[]{
 const keys=[];for(let x=Math.floor((p[0]-radius)/size);x<=Math.floor((p[0]+radius)/size);x++)for(let y=Math.floor((p[1]-radius)/size);y<=Math.floor((p[1]+radius)/size);y++)keys.push(`${x}_${y}`);return keys;
}
export function validateQuery(q:{lon:number;lat:number;radius:number;kind:string}):void{
 if(![400,800,1600].includes(q.radius)||!['projects','applications','zoning','heights'].includes(q.kind))throw new Error('Unsupported query');project(q.lon,q.lat);
}
