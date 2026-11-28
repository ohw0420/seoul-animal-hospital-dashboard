const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const layers=[],maps=[],elements={message:{},map:{}};
function element(){return {style:{setProperty(){}},children:[],appendChild(x){this.children.push(x);},setAttribute(){},addEventListener(name,fn){this[name]=fn;}};}
class LatLng {constructor(lat,lng){this.lat=lat;this.lng=lng;}getLat(){return this.lat;}getLng(){return this.lng;}}
class Bounds {constructor(sw=new LatLng(37.50,126.95),ne=new LatLng(37.58,127.05)){this.sw=sw;this.ne=ne;this.points=[];}extend(p){this.points.push(p);}getSouthWest(){return this.sw;}getNorthEast(){return this.ne;}}
class Layer {constructor(options){this.options=options;this.map=options.map;this.handlers={};layers.push(this);}setMap(map){this.map=map;}setOptions(o){Object.assign(this.options,o);}getBounds(){return new Bounds();}}
class Marker extends Layer{} class Circle extends Layer{} class Polygon extends Layer{} class CustomOverlay extends Layer{}
class Map {
 constructor(node,options){this.center=options.center;this.level=options.level;this.bounds=new Bounds();maps.push(this);}
 getProjection(){return {containerPointFromCoords:p=>({x:400+(p.lng-this.center.lng)*10000,y:300-(p.lat-this.center.lat)*10000})};}
 setCenter(p){this.center=p;}getCenter(){return this.center;}getBounds(){return this.bounds;}
 panTo(p){this.center=p;this.usedPan=true;}getLevel(){return this.level;}
 setLevel(v,options){this.level=v;this.levelOptions=options;}setBounds(){this.level=8;}
}
const row=(name,district,latitude,longitude)=>({name,district,status:'정상영업',phone:'정보 없음',address:'검사 주소',latitude,longitude});
const hospitals=[row('A 병원','A구',37.56,126.99),row('B 병원','B구',37.56,127.02),row('C 병원','C구',37.53,127.02),row('멀리 보이는 D 병원','D구',37.56,127.045)];
const rectangle=(name,w,s,e,n)=>({type:'Feature',properties:{name},geometry:{type:'Polygon',coordinates:[[[w,s],[e,s],[e,n],[w,n],[w,s]]]}});
const boundary={type:'FeatureCollection',features:[rectangle('A구',126.90,37.45,127.01,37.65),rectangle('B구',127.01,37.55,127.04,37.65),rectangle('C구',127.01,37.45,127.04,37.55),rectangle('D구',127.04,37.45,127.10,37.65)]};
let sdk;
const context={console,setTimeout:(fn,ms)=>setTimeout(fn,ms===500?0:ms),clearTimeout,CustomEvent:class{},
 fetch:async()=>({ok:true,json:async()=>boundary}),
 document:{getElementById:id=>elements[id],createElement:element,head:{appendChild:x=>{sdk=x;}}},
 kakao:{maps:{Map,Marker,Circle,Polygon,CustomOverlay,LatLng,LatLngBounds:Bounds,
 MarkerImage:class{},Size:class{},Point:class{},InfoWindow:class{close(){}setContent(){}open(){}},
 load:fn=>fn(),event:{addListener:(obj,name,fn)=>{(obj.handlers??={})[name]=fn;}}}},
};
context.window=context;context.dispatchEvent=()=>{};
context.MAP_INITIAL_DATA={javascriptKey:'TEST',hospitals,districts:[{name:'A구',count:4,latitude:37.56,longitude:126.99}]};
vm.createContext(context);vm.runInContext(fs.readFileSync('static/hospital_map.js','utf8'),context);
const active=Type=>layers.filter(x=>x instanceof Type&&x.map);
const names=()=>active(CustomOverlay).filter(x=>x.options.content.className==='hospital-name');
const tick=()=>new Promise(resolve=>setTimeout(resolve,15));
(async()=>{
 await sdk.onload();await context.HospitalMap.ready;
 assert.equal(active(Polygon).length,4);assert.equal(active(Circle).length,1);assert.equal(active(Marker).length,0);
 let districtQueries=0;context.HospitalMap.onDistrictSelected(()=>{districtQueries++;return Promise.resolve({hospitals:[]});});
 const move=(lat,lng)=>{maps[0].setCenter(new LatLng(lat,lng));maps[0].handlers.dragstart();maps[0].handlers.idle();};
 maps[0].level=6;maps[0].setCenter(new LatLng(37.56,126.99));maps[0].handlers.zoom_changed();maps[0].handlers.idle();
 assert.equal(active(Circle).length,0);assert.equal(active(Marker).length,1);
 assert.equal(active(Marker)[0].options.title,'A 병원');
 assert.equal(names().length,0);assert.equal(districtQueries,0);
 assert.ok(active(Polygon).every(x=>x.options.fillOpacity===0&&x.options.strokeWeight>=1.3));
 move(37.57,127.005); // 중앙에서 50px 떨어진 세로 경계: A+B, 아래 C는 200px 떨어짐
 assert.deepEqual(active(Marker).map(x=>x.options.title).sort(),['A 병원','B 병원']);
 move(37.55,127.005); // 삼거리: A+B+C, 화면에 보이는 D는 원 밖
 assert.deepEqual(active(Marker).map(x=>x.options.title).sort(),['A 병원','B 병원','C 병원']);
 assert.match(elements.message.textContent,/중앙 주변: A구 · B구 · C구/);
 assert.equal(active(Circle).length,0); // 가상 원을 실제로 그리지 않음
 maps[0].level=5;maps[0].handlers.zoom_changed();maps[0].handlers.idle();
 assert.equal(names().length,3);
 move(37.57,127.06);assert.deepEqual(active(Marker).map(x=>x.options.title),['멀리 보이는 D 병원']);
 // 원의 사각 외접 영역에만 걸치는 구는 선택하지 않음(꼭짓점 거리 > 반경).
 move(37.5405,127.0005);assert.deepEqual(active(Marker).map(x=>x.options.title).sort(),['A 병원','C 병원']);
 // 서울 경계 밖이며 가상 원도 닿지 않는 경우.
 move(37.8,127.2);assert.equal(active(Marker).length,0);
 maps[0].level=9;maps[0].handlers.zoom_changed();
 assert.equal(active(Marker).length,0);assert.equal(active(Circle).length,1);
 assert.ok(active(Polygon).every(x=>x.options.fillOpacity===.26));
 context.HospitalMap.update({districts:[14,19,20,29].map((count,i)=>({name:'구'+i,count,latitude:37.56,longitude:126.99}))});
 const circles=active(Circle);
 assert.equal(circles[0].options.fillColor,circles[1].options.fillColor);
 assert.equal(circles[2].options.fillColor,circles[3].options.fillColor);
 assert.notEqual(circles[1].options.fillColor,circles[2].options.fillColor);
 context.HospitalMap.update({districts:[{name:'A구',count:4,latitude:37.56,longitude:126.99}]});
 maps[0].bounds=new Bounds();
 const click=context.HospitalMap.selectDistrict('A구');
 assert.equal(active(Marker).length,0);assert.ok(maps[0].usedPan);
 maps[0].handlers.idle();await tick();await click;
 assert.equal(active(Marker).length,1);assert.equal(districtQueries,0);
 assert.equal(maps[0].levelOptions.animate.duration,420);
 await context.HospitalMap.loadResults(()=>Promise.resolve({hospitals:[hospitals[0]],userLocation:{latitude:37.56,longitude:126.99},radiusM:1000}));
 assert.equal(active(Marker).length,2);assert.equal(active(Circle).length,1);
 assert.equal(active(Circle)[0].options.fillOpacity,.18);assert.equal(active(Circle)[0].options.fillColor,'#bfdbfe');assert.equal(active(Circle)[0].options.strokeWeight,1);
 let release;const waiting=context.HospitalMap.loadResults(()=>new Promise(resolve=>{release=resolve;}));
 context.HospitalMap.showOverview();release({hospitals:[hospitals[0]]});await waiting;
 assert.equal(active(Marker).filter(x=>x.options.title!=='사용자 위치').length,0);
 console.log('PASS: invisible 114px focus circle, single/two/three districts, corner exclusion, outside Seoul, pan refresh, 3 stages, animated click, colors, borders, nearby and stale response');
})().catch(error=>{console.error(error);process.exitCode=1;});
