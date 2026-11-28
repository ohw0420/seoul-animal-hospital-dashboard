import json
import math
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path


class HospitalMapView:
    """병원 지도 표시용 데이터와 HTML을 관리합니다. 담당: 오현우"""

    STATUS_MAP = {
    "영업": "정상영업",
    "정상영업": "정상영업",
    "정상 영업": "정상영업",
    "휴업": "휴업",
    }

    def __init__(self):
        self.hospitals = []
        self.user_location = None
        self.radius_m = None
        self.districts = []

    @staticmethod
    def _coordinates(latitude, longitude):
        """지도에서 사용할 위도·경도를 확인합니다."""
        if isinstance(latitude, bool) or isinstance(longitude, bool):
            raise ValueError("좌표에 참/거짓을 사용할 수 없습니다.")
        latitude = float(latitude)
        longitude = float(longitude)

        if not (
            math.isfinite(latitude)
            and math.isfinite(longitude)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            raise ValueError("올바른 위도·경도가 아닙니다.")

        return latitude, longitude

    def render_hospitals(self, hospitals):
        """병원 목록을 교체합니다. 폐업·알 수 없는 상태·좌표 오류는 제외합니다."""
        result = []

        for hospital in hospitals:
            if not isinstance(hospital, Mapping):
                converter = getattr(hospital, "to_dict", None)
                if not callable(converter):
                    continue
                hospital = converter()
            if not isinstance(hospital, Mapping):
                continue
            status = self.STATUS_MAP.get(str(hospital.get("status", "")).strip())
            if status is None:
                continue

            try:
                latitude, longitude = self._coordinates(
                hospital.get("lat", hospital.get("latitude")),
                hospital.get("lng", hospital.get("longitude")),
                )
            except (TypeError, ValueError, OverflowError):
                continue

            result.append({
                "name": self._text(hospital.get("name"), "이름 없음"),
                "status": status,
                "phone": self._text(hospital.get("phone"), "정보 없음"),
                "address": self._text(hospital.get("address"), "정보 없음"),
                "district": self._text(hospital.get("gu", hospital.get("district")), "지역 미확인"),
                "latitude": latitude,
                "longitude": longitude,
            })

        self.hospitals = result
        return len(result)

    @staticmethod
    def _text(value, fallback):
        if value is None or (isinstance(value, float) and not math.isfinite(value)):
            return fallback
        return str(value).strip() or fallback

    def render_districts(self, districts):
        """담당 클래스에서 집계한 구 이름·병원 수·대표 좌표를 받습니다."""
        result = []
        for district in districts:
            try:
                latitude, longitude = self._coordinates(district['latitude'], district['longitude'])
                count = district['count']
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    continue
                name = self._text(district.get('name'), '')
                if not name:
                    continue
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            result.append(dict(name=name, count=count, latitude=latitude, longitude=longitude))
        self.districts = result
        return len(result)

    def render_district_counts(self, counts):
        """팀원의 전체 자치구 집계에 표시용 대표 좌표를 연결합니다. 집계하지 않습니다.

        counts는 {구 이름: 병원 수}입니다. 빠진 구는 0개로 취급하므로
        필터링하지 않은 서울 전체 집계만 전달해야 합니다.
        """
        if not isinstance(counts, Mapping):
            raise ValueError("자치구 집계는 딕셔너리여야 합니다.")
        path = Path(__file__).resolve().parents[1] / 'static' / 'district_centers.json'
        centers = json.loads(path.read_text(encoding='utf-8'))
        if set(counts) - set(centers):
            raise ValueError("서울 25개 자치구 이름을 사용하세요.")
        for count in counts.values():
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("병원 수는 0 이상의 정수여야 합니다.")
        return self.render_districts([
            dict(name=name, count=counts.get(name, 0), **center)
            for name, center in centers.items()
        ])

    def show_user_location(self, latitude, longitude):
        """전달받은 사용자 좌표를 저장합니다."""
        latitude, longitude = self._coordinates(latitude, longitude)
        self.user_location = {
            "latitude": latitude,
            "longitude": longitude,
        }

    def show_search_radius(self, radius_m):
        """검색 반경을 미터 단위로 저장합니다. 병원을 검색하지는 않습니다."""
        if self.user_location is None:
            raise ValueError("사용자 위치를 먼저 설정하세요.")

        if isinstance(radius_m, bool):
            raise ValueError("반경은 숫자여야 합니다.")
        radius_m = float(radius_m)
        if not math.isfinite(radius_m) or radius_m <= 0:
            raise ValueError("반경은 0보다 큰 숫자여야 합니다.")

        self.radius_m = radius_m

    def clear_user_location(self):
        self.user_location = None
        self.radius_m = None

    def get_display_data(self):
        return deepcopy({
            "hospitals": self.hospitals,
            "userLocation": self.user_location,
            "radiusM": self.radius_m,
            "districts": self.districts,
        })

    def render_html(self, javascript_key):
        """템플릿에 지도 데이터와 JavaScript 키를 전달합니다."""
        if not javascript_key:
            raise ValueError("카카오 JavaScript 키가 필요합니다.")

        template_path = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "map_view.html"
        )
        template = template_path.read_text(encoding="utf-8")

        payload = {
            "javascriptKey": javascript_key,
            **self.get_display_data(),
        }

        # 데이터에 HTML 태그가 있어도 script 태그를 종료하지 못하게 처리합니다.
        serialized = json.dumps(
            payload, ensure_ascii=False, allow_nan=False
        ).replace("<", "\\u003c")

        return template.replace("__MAP_PAYLOAD__", serialized)
