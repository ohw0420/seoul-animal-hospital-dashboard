# 최종 대시보드 통합 기록

## 통합 기준

main 65750e7(PR #2 병합 포함)을 기준으로 오현우 지도 완성본을 연결했습니다. 팀원의 데이터 로딩·좌표 변환·거리 계산·컨트롤러 구현은 유지했습니다. examples/data_classes_demo.py와 tests/test_repository_coordinates.py의 UserLocation import만 현재 최상위 user_location.py에 맞췄습니다.

## 입력과 객체 간 상호작용

초기 실행에서 HospitalRepository(LocationService()).load()로 제공 CSV를 읽고 좌표를 변환합니다. DashboardController.get_district_counts()로 정상영업 집계를 얻고 HospitalMapView가 표시용 대표 좌표를 연결합니다. 병원 객체의 to_dict() 자료는 HospitalMapView를 거쳐 JSON으로 전달됩니다. 브라우저는 화면 중앙의 가상 원과 겹치는 자치구의 병원을 표시합니다.

주소 검색은 화면 입력 → /api/nearby → DashboardController.search_nearby() → LocationService.setUserLocation()·findNearby() → UserLocation → HospitalMapView 순서입니다. 반경의 km 표시를 서버 입력용 미터로 변환하고 기존 컨트롤러 호출 시 km로 전달합니다. 거리·검색 계산은 팀원 구현을 호출합니다.

집계 원은 정상영업 985개 기준이고, 상세 마커는 정상영업·휴업 중 좌표가 유효한 983개가 대상입니다. 좌표 없는 병원은 임의 위치에 표시하지 않습니다. 사용자 위치·반경 결과는 일반 지도 탐색의 자동 구 전환과 별도 모드로 유지합니다.

## 설계와 제안서 대응

6개 Python 클래스의 역할 분리를 유지하며 실제 렌더링은 브라우저 SDK에 위임합니다. 제안서의 메서드명 일부는 실제 구현에서 snake_case 이름과 브라우저 함수로 나뉘었습니다. HospitalMapView.render_hospitals()는 표시 자료 준비, JavaScript popup()은 말풍선 DOM 구성, show_user_location()은 사용자 좌표 저장 역할입니다.

구 선택은 지도 이동·확대를 수행한 뒤 화면 중앙 기준으로 표시할 구를 정합니다. 경계 근처에서는 이웃 구도 표시하는 UX로 구체화했습니다. 병원 자체의 자치구 분류는 Repository가 제공한 gu 값이며 지도 경계 판정과 분리합니다.

## 검증과 한계

로컬 개발 통합본에서 실제 카카오 지도, 구 이동과 확대·축소, 정상영업·휴업 팝업, 공개 시연 주소 검색, 빈 검색 결과, 사용자 위치 삭제, 반경 1~5km 버튼을 확인했습니다. Python 검사는 외부 주소 응답을 고정하고 실제 CSV와 팀원 거리 계산을 사용합니다. 지도 SDK 대역 검사는 단일·두 개·세 개 구 교차, 원의 사각 외접 영역만 겹치는 구 제외, 서울 경계 밖, 단계 전환, 애니메이션, 반경 스타일, 오래된 비동기 응답을 검사합니다.

2013년 참고 경계를 사용하며 최신 행정 경계의 정밀 판정용이 아닙니다. 외부 지도·주소 검색은 인터넷과 키 설정에 의존합니다. 물리적인 cm 크기는 모니터·배율에 따라 달라지므로 가상 원은 114 CSS 픽셀로 고정합니다.

이 문서는 통합 기록이며 최종 보고서·PPT 제출을 대체하지 않습니다. 팀원이 새 ZIP에서 실행을 확인하고 보고서·PPT에 최종 화면과 같은 집계 기준을 반영한 뒤 제출해야 합니다.


## 업로드 브랜치 검사 결과

이 통합 브랜치에서 Python 검사 17개와 지도 SDK 대역 검사를 통과했습니다. 실제 CSV를 사용하는 examples.data_classes_demo도 실행했습니다. 이전 개발 폴더의 검사 19개 중 이번 공식 실행 경로에 포함하지 않은 가상 demo_map.py 관련 HTTP 검사 2개는 제외했습니다. 공식 실행은 map_preview.py로 통일했습니다.
