# 서울시 동물병원 지도

객체지향프로그래밍 11조 팀 프로젝트입니다. 서울시 동물병원 인허가 데이터를 처리하고 카카오 지도에 병원 분포와 영업 상태를 표시합니다.

## 실행 방법

Python 3.11에서 검증했습니다. GitHub에서 이 브랜치의 ZIP을 내려받아 압축을 풀고, map_preview.py가 있는 폴더를 VS Code로 엽니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

프로젝트 최상위의 .env.example을 복사해 .env를 만들고 KAKAO_JAVASCRIPT_KEY에 JavaScript 키를 입력합니다. 카카오 앱에서 http://localhost:8000 도메인을 허용해야 합니다. KAKAO_API_KEY는 주소 검색용 선택 REST API 키이며 JavaScript 키와 다릅니다. 설정하지 않으면 팀원의 Nominatim 주소 검색을 사용합니다. .env와 실제 키는 GitHub에 올리지 않습니다.

```powershell
.\.venv\Scripts\python.exe map_preview.py
```

브라우저에서 http://localhost:8000 에 접속합니다. 종료는 터미널에서 Ctrl+C입니다. 지도와 주소 검색에 인터넷 연결이 필요합니다. HTML 파일을 직접 열지 않습니다. localhost는 실행한 컴퓨터에서 사용하는 주소이며 외부 공유용 공개 주소가 아닙니다.

## 대시보드 기능

- 서울 25개 자치구의 정상영업 병원 수를 면적이 비례하는 원으로 표시합니다.
- 원은 같은 파란색 계열에서 10개 단위로 진해집니다.
- 구 경계 또는 원을 선택하면 해당 구 중심으로 이동·확대합니다.
- 집계 원 → 병원 마커 → 더 확대하면 병원 이름 순서로 전환합니다.
- 상세 지도는 화면 중앙의 보이지 않는 반경 114 CSS 픽셀 원과 겹치는 구들의 병원을 표시합니다. 구 안쪽에서는 한 구, 경계 근처에서는 여러 구를 표시합니다. 구 경계는 유지하고 내부 채움은 제거합니다.
- 정상영업은 초록색, 휴업은 빨간색으로 표시하며 폐업·기타 상태와 좌표 오류는 제외합니다.
- 병원 마커를 누르면 이름·영업 상태·전화번호·주소를 확인합니다.
- 주소 검색 결과에 사용자 위치와 연한 파란색 검색 반경, 반경 내 병원을 표시합니다.
- 검색 반경은 −/+ 버튼으로 1~5km 사이를 0.5km씩 조절합니다.
- 사용자 위치 삭제와 서울 전체 보기, 검색 결과 없음·오류 안내를 지원합니다.

## 사용 데이터와 집계 기준

[서울시 동물병원 인허가 정보](https://data.seoul.go.kr/dataList/OA-16007/S/1/datasetView.do)를 사용합니다. 출처·날짜·인코딩·전처리 기준은 [데이터 안내](data/README.md)에 기록했습니다.

제공 CSV 2,242건 중 정상영업 985건, 휴업 10건입니다. 집계 원은 정상영업 985건 기준이며 상세 지도 대상은 정상영업·휴업 중 좌표가 유효한 983건입니다. 상태와 좌표 포함 기준이 달라 집계 숫자와 마커 수가 다를 수 있습니다. 행정상 영업 상태이며 실시간 진료 여부가 아닙니다.

구 경계는 2013년 단순화 참고 자료입니다. 병원의 자치구는 주소를 처리하는 HospitalRepository가 제공하며 경계로 재분류하지 않습니다. [경계 출처·라이선스](static/BOUNDARY_LICENSE.txt)를 참고하세요.

## 클래스 설계와 역할

| 담당자 | 클래스 | 역할 |
|---|---|---|
| 이승훈 | AnimalHospital, HospitalRepository | pandas 로딩·정리, 병원 객체, 자치구 조회·집계·검색 자료 |
| 정부성 | LocationService, UserLocation | 주소·좌표 변환, 거리 계산, 사용자 위치, 발표 |
| 오현우 | HospitalMapView | 지도·집계 원·마커·팝업·반경 표시, 통합 정리·보고서 |
| 이지운 | DashboardController | 입력에 따른 기능 연결·조회, PPT |

실제 위치 클래스는 최상위 location_service.py와 user_location.py를 사용합니다. src/location_service.py와 src/user_location.py는 초기 틀이며 이번 실행에서 사용하지 않습니다.

CSV → HospitalRepository.load(LocationService 연결) → AnimalHospital 객체 → DashboardController 집계·주변 검색 → HospitalMapView 표시 자료 → JSON → 브라우저 카카오 지도 순서로 동작합니다.

HospitalMapView는 표시 자료를 검증하며 데이터 로딩·주소 검색·거리 계산을 구현하지 않습니다. map_preview.py는 팀원 클래스들을 호출하는 통합 시연 서버입니다. static/map_controls.js는 화면 입력을 시연 서버와 연결하고 static/hospital_map.js는 지도와 화면 중앙의 표시 대상 구를 관리합니다. Python 클래스가 표시 자료를 관리하고 브라우저 SDK가 실제 지도를 그립니다.

[통합 구조와 검증](docs/final_integration.md), [데이터 클래스 상세](docs/data_classes.md)를 참고하세요.

## 검사

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Node.js가 설치된 환경에서는 다음으로 지도 SDK 대역 검사를 실행할 수 있습니다. Node.js는 실제 지도 실행에는 필요하지 않습니다.

```powershell
node tests/map_browser_test.cjs
```

검사는 고정 주소 응답을 사용하므로 외부 주소 검색의 가용성을 보장하지 않습니다. 실제 지도 표시는 JavaScript 키와 허용 도메인을 설정한 브라우저에서 별도로 확인해야 합니다.

## 현재 공개 범위

저장소에서 내려받아 실행하는 임시 최종 통합본입니다. 외부 호스팅 배포는 포함하지 않습니다. static/index.html은 이전 지도 파일이며 공식 실행 경로는 map_preview.py입니다.
