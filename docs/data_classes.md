# 병원 모델과 데이터 저장소 사용법

담당: 이승훈 — AnimalHospital, HospitalRepository

## 전처리만 실행하기

프로젝트 최상위에서 실행합니다. 필요한 패키지는 기존 requirements.txt의 pandas입니다.

```python
from src.hospital_repository import HospitalRepository

repository = HospitalRepository()
repository.load("data/seoul_animal_hospitals.csv")

print(repository.report)
print(repository.find_all()[0])
print(repository.get_all()[0])
```

HospitalRepository는 pandas로 CSV를 읽고 공백·누락·중복·상태·주소·좌표를 정리한 뒤 AnimalHospital 객체를 만듭니다. 지도·주소 검색·API 키 없이 전처리와 조회를 실행할 수 있습니다.

## 병원 객체 목록 조회

```python
all_hospitals = repository.find_all()
mapo_hospitals = repository.find_by_district("마포구")

for hospital in mapo_hospitals:
    if hospital.is_displayable() and hospital.has_coordinates():
        print(hospital.name, hospital.latitude, hospital.longitude)
        print(hospital.get_display_info())
```

- `find_all()` / `find_by_district()`: AnimalHospital 객체 목록을 반환하며 폐업·기타 상태도 포함합니다.
- `is_closed()`: 폐업 여부만 확인합니다.
- `is_displayable()`: 정상 영업 또는 휴업인지 확인합니다.
- `has_coordinates()`: 지도에 사용할 유효한 위경도가 있는지 확인합니다.
- `get_display_info()`: 병원명·영업상태·전화번호·주소를 반환합니다.
- 병원 객체 내부의 상태는 `정상 영업`, `휴업`, `폐업`, `기타 상태`입니다. 생성 후 속성 재대입은 불가합니다.

## 현재 컨트롤러용 딕셔너리 목록 조회

```python
records = repository.get_all()
opened = [h for h in records if h["status"] == "영업"]
```

현재 DashboardController의 `get_all()` 호출과 딕셔너리 접근에 맞춘 반환 형식입니다. 객체용 조회 API와 별도이므로 한 목록에서 두 접근 방식을 혼용하지 마세요.

| 키 | 내용 |
|---|---|
| id | 관리번호 문자열 |
| name | 병원명 |
| status | 컨트롤러용 상태: 영업 / 휴업 / 폐업 / 기타 상태 |
| status_label | 표시용 상태: 정상 영업 / 휴업 / 폐업 / 기타 상태 |
| phone | 전화번호, 없으면 빈 문자열 |
| address | 도로명주소 우선, 없으면 지번주소 |
| gu | 서울 자치구 또는 지역 미확인 |
| lat / lng | 변환된 위도·경도 또는 None |
| x / y | 원본 좌표 또는 None |

get_all()은 새 딕셔너리를 생성하므로 반환값 수정이 저장소의 병원 정보를 바꾸지 않습니다. `json.dumps()`로 직렬화할 수 있으나, 실제 지도 HTML에 전달하는 연결은 화면 담당 코드에서 구현해야 합니다.

## 위치 서비스 연결 규칙

```python
from src.location_service import LocationService
from src.hospital_repository import HospitalRepository

service = LocationService()  # 위치 담당자가 구현한 생성 방식에 맞춰 설정
repository = HospitalRepository(service)
repository.load("data/seoul_animal_hospitals.csv")
```

서비스는 `convert_coordinates(x, y)` 메서드를 제공해야 하고, 결과는 `(위도, 경도)` 또는 변환 불가 시 `None`입니다. 위치 서비스 없이 저장소를 생성하면 원본 X/Y를 보관하되 lat/lng는 None으로 남깁니다. 서비스가 준비되면 연결한 저장소에서 데이터를 다시 로딩하세요.

현재 컨트롤러의 `only_open=True`는 정상 영업만 선택합니다. 휴업도 지도에 표시하려면 컨트롤러의 필터 조건을 별도로 맞춰야 합니다. 위치 변환, 지도 연결, 반경 검색은 각 담당자와 통합해야 하는 후속 작업입니다.
