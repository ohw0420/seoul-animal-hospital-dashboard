/* 지도 시연 서버와 화면 연결. 조회·주소 변환·거리 계산은 서버의 팀원 코드를 호출합니다. */
(async () => {
  await HospitalMap.ready;
  const select = document.getElementById('district-select');
  for (const district of [...MAP_INITIAL_DATA.districts].sort((a,b)=>a.name.localeCompare(b.name,'ko'))) {
    const option = document.createElement('option');
    option.value = district.name; option.textContent = district.name; select.appendChild(option);
  }
  document.getElementById('real-controls').hidden = false;
  const radius = document.getElementById('radius');
  const decrease = document.getElementById('radius-decrease');
  const increase = document.getElementById('radius-increase');
  function changeRadius(step) {
    const value = Math.max(1000, Math.min(5000, Number(radius.value) + step));
    radius.value = String(value);
    document.getElementById('radius-display').textContent = `${value / 1000}km`;
    decrease.disabled = value === 1000;
    increase.disabled = value === 5000;
  }
  decrease.addEventListener('click', () => changeRadius(-500));
  increase.addEventListener('click', () => changeRadius(500));
  changeRadius(0);
  async function jsonRequest(url, options) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '조회에 실패했습니다.');
    return data;
  }
  select.addEventListener('change', () => HospitalMap.selectDistrict(select.value));
  document.getElementById('overview-button').addEventListener('click', () => HospitalMap.showOverview({fit:true}));
  document.getElementById('clear-user-button').addEventListener('click', () => {
    // 주변 결과는 지운 사용자 위치에 종속되므로 함께 전체 보기로 돌아갑니다.
    HospitalMap.update({userLocation:null,radiusM:null});
    HospitalMap.showOverview({fit:true});
  });
  window.addEventListener('hospitalmap:viewchange', event => {
    select.value = event.detail.selectedDistrict || '';
  });
  document.getElementById('nearby-form').addEventListener('submit', async event => {
    event.preventDefault();
    const address = document.getElementById('address').value.trim();
    const radiusM = Number(document.getElementById('radius').value);
    const button = document.getElementById('search-button');
    button.disabled = true;
    try {
      await HospitalMap.loadResults(() => jsonRequest('/api/nearby', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({address,radiusM}),
      }));
    } finally {button.disabled = false;}
  });
})();
