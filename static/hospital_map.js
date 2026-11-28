/* 표시 전용: 조회·주소 변환·거리 계산은 외부 담당자가 수행합니다. */
(() => {
  'use strict';
  const message = document.getElementById('message');
  let current = window.MAP_INITIAL_DATA;
  const mapHospitals = current.hospitals || [];
  let map, infoWindow, userMarker, radiusCircle, onSelect;
  let hospitalMarkers = [], districtLayers = [], version = 0;
  let hospitalNameLayers = [];
  let viewportChanged = false;
  let changingViewport = false;
  let cameraWait = null;
  let cameraTimer = null;
  let cameraPhase = null;
  let cameraTarget = null;
  let cameraZoomLevel = null;
  let boundaries = null;
  let countLabels = [];
  // 카카오 지도는 level 값이 커질수록 축소됩니다.
  const OVERVIEW_LEVEL = 9;
  const DISTRICT_LEVEL = 7;
  // 약 3cm(96 CSS px/in 기준). 지도 거리와 무관한 화면 중앙의 가상 원입니다.
  const FOCUS_RADIUS_PX = 114;
  let summaryFitLevel = 8;
  const COUNT_COLORS = [96,91,84,76,66,55,44,35,27,19,12].map(lightness=>`hsl(207, 75%, ${lightness}%)`);
  function countBucket(count) { return Math.min(COUNT_COLORS.length-1, Math.floor(Math.max(0,count)/10)); }
  function hospitalLevel() { return Math.min(DISTRICT_LEVEL,summaryFitLevel-2); }
  function districtAt(location) {
    if(!location||!boundaries)return null;
    const x=location.getLng?location.getLng():location.lng;
    const y=location.getLat?location.getLat():location.lat;
    function inside(ring) {
      let found=false;
      for(let i=0,j=ring.length-1;i<ring.length;j=i++) {
        const [xi,yi]=ring[i], [xj,yj]=ring[j];
        if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/(yj-yi)+xi)found=!found;
      }
      return found;
    }
    for(const feature of boundaries.features) {
      const polygons=feature.geometry.type==='MultiPolygon'?feature.geometry.coordinates:[feature.geometry.coordinates];
      if(polygons.some(rings=>inside(rings[0])&&!rings.slice(1).some(inside)))return feature.properties.name;
    }
    return null;
  }
  function focusedDistricts() {
    if(!boundaries||!map.getProjection)return [];
    const projection=map.getProjection();
    const center=projection.containerPointFromCoords(map.getCenter());
    const radiusSquared=FOCUS_RADIUS_PX**2;
    function inside(ring) {
      let found=false;
      for(let i=0,j=ring.length-1;i<ring.length;j=i++) {
        const a=ring[i],b=ring[j];
        if((a.y>center.y)!==(b.y>center.y)&&center.x<(b.x-a.x)*(center.y-a.y)/(b.y-a.y)+a.x)found=!found;
      }
      return found;
    }
    function touches(ring) {
      for(let i=0,j=ring.length-1;i<ring.length;j=i++) {
        const a=ring[j],b=ring[i],dx=b.x-a.x,dy=b.y-a.y;
        const t=dx||dy?Math.max(0,Math.min(1,((center.x-a.x)*dx+(center.y-a.y)*dy)/(dx*dx+dy*dy))):0;
        if((a.x+t*dx-center.x)**2+(a.y+t*dy-center.y)**2<=radiusSquared)return true;
      }
      return false;
    }
    return boundaries.features.filter(feature=>{
      const polygons=feature.geometry.type==='MultiPolygon'?feature.geometry.coordinates:[feature.geometry.coordinates];
      return polygons.some(rings=>{
        const projected=rings.map(ring=>ring.map(([lng,lat])=>projection.containerPointFromCoords(new kakao.maps.LatLng(lat,lng))));
        return (inside(projected[0])&&!projected.slice(1).some(inside))||projected.some(touches);
      });
    }).map(feature=>feature.properties.name);
  }
  let overview = !current.selectedDistrict;
  let fittingNearby = false;
  let resolveReady;
  const ready = new Promise(resolve => {resolveReady = resolve;});
  function notifyView() {
    window.dispatchEvent(new CustomEvent('hospitalmap:viewchange', {
      detail:{selectedDistrict:current.selectedDistrict || null, viewMode:overview?'overview':current.viewMode || 'district'},
    }));
  }
  function image(color,compact=false) {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="40"><path d="M16 39C13 33 2 23 2 16a14 14 0 1 1 28 0c0 7-11 17-14 23" fill="${color}" stroke="white" stroke-width="2"/><circle cx="16" cy="16" r="5" fill="white"/></svg>`;
    const width=compact?22:32,height=compact?28:40;
    return new kakao.maps.MarkerImage('data:image/svg+xml;charset=UTF-8,'+encodeURIComponent(svg),new kakao.maps.Size(width,height),{offset:new kakao.maps.Point(width/2,height)});
  }
  function popup(h) {
    const box=document.createElement('div'); box.className='popup';
    const title=document.createElement('strong'); title.textContent=h.name; box.appendChild(title);
    for(const text of [`영업 상태: ${h.status}`,`전화번호: ${h.phone}`,`주소: ${h.address}`]) {
      const row=document.createElement('div'); row.textContent=text; box.appendChild(row);
    }
    return box;
  }
  function refreshCountLabels() {
    const showNames = map.getLevel() < summaryFitLevel;
    for (const item of countLabels) {
      let radiusPx = item.count ? 170 * Math.sqrt(item.count) / (0.3 * 2 ** map.getLevel()) : 10;
      if (item.circle && map.getProjection) {
        const projection = map.getProjection();
        const center = projection.containerPointFromCoords(item.position);
        const edge = projection.containerPointFromCoords(item.circle.getBounds().getNorthEast());
        radiusPx = Math.abs(edge.y - center.y);
      }
      item.button.style.setProperty('--circle-radius', `${radiusPx}px`);
      item.number.style.fontSize = `${Math.max(10, Math.min(23, radiusPx * 0.9))}px`;
      item.name.hidden = !showNames;
    }
  }
  function draw({fit = false} = {}) {
    infoWindow.close();
    for(const layer of [...hospitalMarkers,...districtLayers]) layer.setMap(null);
    for(const layer of hospitalNameLayers)layer.setMap(null);
    hospitalNameLayers=[];
    hospitalMarkers=[]; districtLayers=[];
    countLabels=[];
    if(userMarker) userMarker.setMap(null);
    if(radiusCircle) radiusCircle.setMap(null);
    userMarker=radiusCircle=null;
    const bounds=new kakao.maps.LatLngBounds();
    const seoulBounds=new kakao.maps.LatLngBounds(); let points=0;
    const nameBoxes=[];
    let viewportBox=null;
    let onScreenCount=0;
    if(current.viewMode==='viewport'&&map.getBounds) {
      const area=map.getBounds(),sw=area.getSouthWest(),ne=area.getNorthEast();
      viewportBox={south:sw.getLat(),west:sw.getLng(),north:ne.getLat(),east:ne.getLng()};
    }
    function withinViewport(h,padding=0) {
      if(!viewportBox)return true;
      const b=viewportBox,dy=(b.north-b.south)*padding,dx=(b.east-b.west)*padding;
      return h.latitude>=b.south-dy&&h.latitude<=b.north+dy&&h.longitude>=b.west-dx&&h.longitude<=b.east+dx;
    }
    for(const h of overview && (current.districts || []).length ? [] : current.hospitals || []) {
      // 화면 밖 10%를 미리 준비해 가장자리에서 마커가 갑자기 생기는 현상을 줄입니다.
      if(!withinViewport(h,.1))continue;
      const onScreen=withinViewport(h);
      if(onScreen)onScreenCount++;
      const position=new kakao.maps.LatLng(h.latitude,h.longitude);
      const marker=new kakao.maps.Marker({map,position,title:h.name,image:image(h.status==='휴업'?'#dc2626':'#15803d',map.getLevel()>hospitalLevel()-1)});
      hospitalMarkers.push(marker);
      let canShowName=true;
      if(map.getProjection&&onScreen) {
        const p=map.getProjection().containerPointFromCoords(position);
        const width=Math.min(140,Math.max(40,Array.from(h.name).reduce((sum,c)=>sum+(c.charCodeAt(0)>127?11:6),10)));
        const box={left:p.x-width/2,right:p.x+width/2,top:p.y+5,bottom:p.y+25};
        canShowName=!nameBoxes.some(other=>box.left<other.right+4&&box.right>other.left-4&&box.top<other.bottom+3&&box.bottom>other.top-3);
        if(canShowName)nameBoxes.push(box);
      }
      if(onScreen&&canShowName&&map.getLevel()<=hospitalLevel()-1) {
        const name=document.createElement('button');name.className='hospital-name';name.textContent=h.name;name.title=h.name;
        name.setAttribute('aria-label',`${h.name} 상세정보`);
        name.addEventListener('click',()=>{infoWindow.setContent(popup(h));infoWindow.open(map,marker);});
        hospitalNameLayers.push(new kakao.maps.CustomOverlay({map,position,content:name,xAnchor:.5,yAnchor:0,zIndex:3}));
      }
      kakao.maps.event.addListener(marker,'click',()=>{infoWindow.setContent(popup(h));infoWindow.open(map,marker);});
      bounds.extend(position); points++;
    }
    if(boundaries) for(const feature of boundaries.features) {
      const name=feature.properties.name;
      const polygons=feature.geometry.type==='MultiPolygon'?feature.geometry.coordinates:[feature.geometry.coordinates];
      for(const rings of polygons) {
        const path=rings.map(ring=>ring.map(([lng,lat])=>new kakao.maps.LatLng(lat,lng)));
        const selected = current.viewMode==='viewport'?(current.focusedDistricts||[]).includes(name):current.selectedDistrict===name;
        const polygon=new kakao.maps.Polygon({map,path,strokeWeight:overview?1.3:selected?2.4:1.3,strokeColor:selected?'#285778':'#667f92',strokeOpacity:overview?.85:selected?.95:.72,fillColor:'#7fa8c4',fillOpacity:overview?.26:0,zIndex:0});
        districtLayers.push(polygon);
        kakao.maps.event.addListener(polygon,'click',()=>selectDistrict(name));
        kakao.maps.event.addListener(polygon,'mouseover',()=>polygon.setOptions({strokeWeight:overview?2.5:selected?2.4:1.8,fillOpacity:overview?.39:0}));
        kakao.maps.event.addListener(polygon,'mouseout',()=>polygon.setOptions({strokeWeight:overview?1.3:selected?2.4:1.3,fillOpacity:overview?.26:0}));
        if(overview) for(const point of path[0]){bounds.extend(point);seoulBounds.extend(point);}
      }
      if(overview)points++;
    }
    for(const d of current.districts || []) {
      if(!overview)break;
      const position=new kakao.maps.LatLng(d.latitude,d.longitude);
      // 면적이 병원 수에 비례하도록 반지름에는 제곱근을 사용합니다.
      let circle = null;
      if(d.count>0) {
        const fill = COUNT_COLORS[countBucket(d.count)];
        circle=new kakao.maps.Circle({map,center:position,radius:170*Math.sqrt(d.count),strokeColor:'#ffffff',strokeWeight:1.5,strokeOpacity:.9,fillColor:fill,fillOpacity:.85,zIndex:1});
        districtLayers.push(circle);
        kakao.maps.event.addListener(circle,'click',()=>selectDistrict(d.name));
      }
      const button=document.createElement('button');button.className='district-count';
      if(d.count===0)button.className+=' is-zero';
      button.title=`${d.name} · 정상영업 ${d.count}개`;
      button.setAttribute('aria-label',`${d.name} 병원 ${d.count}개 선택`);
      const number=document.createElement('span');number.className='district-count-number';number.textContent=String(d.count);
      if(countBucket(d.count)<=5)number.className+=' dark-number';
      const name=document.createElement('span');name.className='district-count-name';name.textContent=d.name;
      button.appendChild(number);button.appendChild(name);
      button.addEventListener('click',()=>selectDistrict(d.name));
      // 중앙점과 숫자의 중심을 정확히 맞추고, 구 이름은 원 아래에 둡니다.
      districtLayers.push(new kakao.maps.CustomOverlay({map,position,content:button,xAnchor:.5,yAnchor:.5,zIndex:2}));
      countLabels.push({button,number,name,circle,position,count:d.count});
      bounds.extend(position);points++;
    }
    if(current.userLocation) {
      const position=new kakao.maps.LatLng(current.userLocation.latitude,current.userLocation.longitude);
      userMarker=new kakao.maps.Marker({map,position,title:'사용자 위치',image:image('#2563eb')});
      bounds.extend(position); points++;
      if(current.radiusM>0) {
        radiusCircle=new kakao.maps.Circle({map,center:position,radius:current.radiusM,strokeWeight:1,strokeColor:'#93c5fd',strokeOpacity:.65,fillColor:'#bfdbfe',fillOpacity:.18});
        bounds.extend(radiusCircle.getBounds().getSouthWest()); bounds.extend(radiusCircle.getBounds().getNorthEast());
      }
    }
    // 마커만 갱신할 때 사용자가 조절한 지도 위치와 확대 수준을 유지합니다.
    if(fit) {
      if(points===0){map.setCenter(new kakao.maps.LatLng(37.5665,126.978));map.setLevel(OVERVIEW_LEVEL);}
      else if(points===1&&!radiusCircle&&!districtLayers.length){map.setCenter(bounds.getSouthWest());map.setLevel(4);}
      // 집계 원의 크기로 범위를 늘리지 않고 서울 경계 자체를 가까이 맞춥니다.
      else map.setBounds(overview&&boundaries?seoulBounds:bounds,12,12,12,12);
      if(overview)summaryFitLevel=map.getLevel();
    }
    refreshCountLabels();
    const displayed=current.viewMode==='viewport'?onScreenCount:hospitalMarkers.length;
    message.textContent=(current.label?current.label+' · ':'')+(overview&&(current.districts||[]).length?'구 경계 또는 원을 선택하세요.':displayed?'병원 '+displayed+'개 표시 중':'표시할 병원이 없습니다.');
  }

  function finishCamera() {
    clearTimeout(cameraTimer);
    changingViewport=false;
    cameraPhase=null;cameraTarget=null;cameraZoomLevel=null;
    if(cameraWait){const resolve=cameraWait;cameraWait=null;resolve();}
  }
  function cameraAtTarget() {
    if(!cameraTarget||!map.getCenter)return false;
    const center=map.getCenter();
    const lat=p=>p.getLat?p.getLat():p.lat;
    const lng=p=>p.getLng?p.getLng():p.lng;
    return Math.abs(lat(center)-lat(cameraTarget))<.00001&&Math.abs(lng(center)-lng(cameraTarget))<.00001;
  }
  function advanceCamera() {
    if(!changingViewport||!cameraTarget)return;
    clearTimeout(cameraTimer);
    if(!cameraAtTarget())map.setCenter(cameraTarget);
    const level=map.getLevel();
    if(level===cameraZoomLevel){finishCamera();return;}
    cameraPhase='zoom';
    // 카카오 SDK는 두 단계 이하의 확대 차이에 애니메이션을 지원합니다.
    const step=level+Math.sign(cameraZoomLevel-level)*Math.min(2,Math.abs(cameraZoomLevel-level));
    map.setLevel(step,{animate:{duration:420}});
    cameraTimer=setTimeout(advanceCamera,500);
  }
  function focusDistrict(name) {
    finishCamera();
    changingViewport=true;
    const completed=new Promise(resolve=>{cameraWait=resolve;});
    const center=(current.districts || []).find(d=>d.name===name);
    if(center) {
      cameraTarget=new kakao.maps.LatLng(center.latitude,center.longitude);
      cameraZoomLevel=hospitalLevel();cameraPhase='pan';
      // 먼저 부드럽게 중심으로 이동하고, 그 완료 뒤 확대 모션을 이어 갑니다.
      if(cameraAtTarget())advanceCamera();
      else {map.panTo(cameraTarget);cameraTimer=setTimeout(advanceCamera,650);}
    } else {
      const feature=boundaries?.features.find(f=>f.properties.name===name);
      if(feature) {
      const polygons=feature.geometry.type==='MultiPolygon'?feature.geometry.coordinates:[feature.geometry.coordinates];
      const bounds=new kakao.maps.LatLngBounds();
      for(const rings of polygons)for(const [lng,lat] of rings[0])bounds.extend(new kakao.maps.LatLng(lat,lng));
      map.setBounds(bounds);
      if(map.getLevel()>=OVERVIEW_LEVEL)map.setLevel(OVERVIEW_LEVEL-1);
      }
      cameraTimer=setTimeout(finishCamera,650);
    }
    return completed;
  }

  function showOverview({fit = false} = {}) {
    ++version; // 진행 중인 구별 조회 응답도 취소한 것으로 처리합니다.
    finishCamera();
    overview=true;
    current={...current,selectedDistrict:null,viewMode:'overview',hospitals:[],label:''};
    draw({fit});
    notifyView();
  }

  async function selectDistrict(name,{focus=true}={}) {
    if(!name){showOverview({fit:true});return;}
    if(focus) {
      const movement=++version;
      overview=false;
      current={...current,selectedDistrict:null,viewMode:'moving',hospitals:[],label:''};
      draw();message.textContent=`${name} 중심으로 이동하는 중입니다.`;
      await focusDistrict(name);
      if(movement!==version)return;
      return syncViewportHospitals();
    }
    const request=++version;
    overview=false;
    current={...current,selectedDistrict:name,viewMode:'district',hospitals:[],label:name};
    draw();
    notifyView();
    if(!onSelect){message.textContent=`${name||'서울 전체'} 선택됨 · 조회 연결이 필요합니다.`;window.dispatchEvent(new CustomEvent('hospitalmap:district',{detail:{name}}));return;}
    message.textContent='병원 정보를 불러오는 중입니다.';
    try {
      const payload=await onSelect(name);
      if(request!==version)return;
      if(!payload||!Array.isArray(payload.hospitals))throw new Error('표시 데이터 형식 오류');
      // 조회 응답은 표시 자료만 갱신하며 확대 수준을 다시 설정하지 않습니다.
      current={...current,...payload,selectedDistrict:name};draw();
    }catch(error){if(request===version)message.textContent=error.message || '병원 조회에 실패했습니다. 다시 선택해주세요.';}
  }

  function syncViewportHospitals() {
    if(map.getLevel()>hospitalLevel()) {
      if(!overview)showOverview();else refreshCountLabels();
      return;
    }
    ++version;
    overview=false;
    // 화면 중앙의 가상 원과 면적이 겹치는 구만 선택합니다. 원은 그리지 않습니다.
    const names=focusedDistricts(), selected=new Set(names);
    current={...current,selectedDistrict:districtAt(map.getCenter?map.getCenter():null),
      focusedDistricts:names,hospitals:mapHospitals.filter(h=>selected.has(h.district)),
      viewMode:'viewport',label:names.length?'중앙 주변: '+names.join(' · '):'중앙 주변에 서울 자치구가 없습니다'};
    draw();notifyView();
  }

  async function loadResults(fetchResults) {
    const request=++version;
    finishCamera();
    message.textContent='주소와 주변 병원을 확인하는 중입니다.';
    try {
      const payload=await fetchResults();
      if(request!==version)return false;
      if(!payload||!Array.isArray(payload.hospitals))throw new Error('표시 데이터 형식을 확인하세요.');
      current={...current,...payload,viewMode:'nearby',selectedDistrict:null};
      overview=false;
      // 검색 범위를 맞추는 자동 축소를 사용자의 축소로 오인하지 않습니다.
      fittingNearby=true;
      draw({fit:true});
      notifyView();
      setTimeout(()=>{fittingNearby=false;},800);
      return true;
    }catch(error){
      if(request===version)message.textContent=error.message || '주변 검색에 실패했습니다.';
      return false;
    }
  }
  window.HospitalMap={
    ready,
    update(payload){
      ++version;
      finishCamera();
      const previous=current.selectedDistrict;
      current={...current,...payload};
      if(Object.prototype.hasOwnProperty.call(payload,'selectedDistrict'))overview=!payload.selectedDistrict;
      if(payload.viewMode==='nearby')overview=false;
      if(map){draw();if(current.selectedDistrict&&previous!==current.selectedDistrict)focusDistrict(current.selectedDistrict);}
      notifyView();
    },
    showOverview,
    loadResults,
    onDistrictSelected(callback){onSelect=callback;},
    selectDistrict,
  };
  const timeout=setTimeout(()=>{message.textContent='지도 로딩이 지연됩니다. 인터넷 연결과 지도 사용 설정을 확인하세요.';},15000);
  const sdk=document.createElement('script');
  sdk.src='https://dapi.kakao.com/v2/maps/sdk.js?autoload=false&appkey='+encodeURIComponent(current.javascriptKey);
  sdk.onerror=()=>{clearTimeout(timeout);message.textContent='지도 로딩 실패: 인터넷 연결, JavaScript 키와 허용 도메인을 확인하세요.';};
  sdk.onload=()=>{
    if(!window.kakao||!kakao.maps){clearTimeout(timeout);message.textContent='카카오 지도 사용 설정을 확인하세요.';return;}
    kakao.maps.load(async ()=>{
      try {
        map=new kakao.maps.Map(document.getElementById('map'),{center:new kakao.maps.LatLng(37.5665,126.978),level:8});
        infoWindow=new kakao.maps.InfoWindow({removable:true});
        kakao.maps.event.addListener(map,'click',()=>infoWindow.close());
        kakao.maps.event.addListener(map,'zoom_changed',()=>{
          // 축소 시 전체 표시로 돌아갑니다. 다시 확대되지 않도록 여기서는 setBounds를 호출하지 않습니다.
          if(changingViewport)return;
          if(!overview&&!fittingNearby&&map.getLevel()>hospitalLevel())showOverview();
          else if(overview)refreshCountLabels();
          viewportChanged=true;
        });
        kakao.maps.event.addListener(map,'dragstart',()=>{viewportChanged=true;});
        kakao.maps.event.addListener(map,'idle',()=>{
          if(changingViewport){
            viewportChanged=false;
            if(cameraPhase==='pan'&&cameraAtTarget())advanceCamera();
            else if(!cameraPhase)finishCamera();
            return;
          }
          if(viewportChanged){
            viewportChanged=false;
            if(!fittingNearby&&current.viewMode!=='nearby')syncViewportHospitals();else draw();
          }else if(overview)refreshCountLabels();
        });
        clearTimeout(timeout);
        let boundaryFailed=false;
        try {
          const response=await fetch('/static/seoul_districts.geojson');
          if(!response.ok)throw new Error();
          const result=await response.json();
          if(!Array.isArray(result.features))throw new Error();
          boundaries=result;
        }catch(_){boundaryFailed=true;}
        draw({fit:true});if(current.selectedDistrict)focusDistrict(current.selectedDistrict);
        if(boundaryFailed)message.textContent+=' · 구 경계 로딩 실패 (다시 접속해주세요)';resolveReady();
        // 입력창 표시나 창 크기 변경 후에도 서울 전체가 지도 영역에 맞도록 합니다.
        if(typeof ResizeObserver!=='undefined') {
          let resizeTimer;
          const observer=new ResizeObserver(()=>{
            clearTimeout(resizeTimer);
            resizeTimer=setTimeout(()=>{map.relayout();if(current.viewMode==='viewport')syncViewportHospitals();else draw({fit:overview});},120);
          });
          observer.observe(document.getElementById('map'));
        }
      }catch(_){clearTimeout(timeout);message.textContent='지도 초기화 실패: 지도 설정과 전달 데이터를 확인하세요.';}
    });
  };
  document.head.appendChild(sdk);
})();
