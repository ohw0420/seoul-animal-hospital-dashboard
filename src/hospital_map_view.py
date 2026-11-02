import json
import math
from pathlib import Path


class HospitalMapView:
    """병원 지도 표시용 데이터와 HTML을 관리합니다. 담당: 오현우"""

    STATUS_MAP = {
        "영업": "정상영업",
        "정상영업": "정상영업",
        "휴업": "휴업",
    }

    def __init__(self):
        self.hospitals = []
        self.user_location = None
        self.radius_m = None

    @staticmethod
    def _coordinates(latitude, longitude):
        """지도에서 사용할 위도·경도를 확인합니다."""
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
            status = self.STATUS_MAP.get(hospital.get("status"))
            if status is None:
                continue

            try:
                latitude, longitude = self._coordinates(
                    hospital.get("latitude"),
                    hospital.get("longitude"),
                )
            except (TypeError, ValueError):
                continue

            result.append({
                "name": str(hospital.get("name") or "이름 없음"),
                "status": status,
                "phone": str(hospital.get("phone") or "정보 없음"),
                "address": str(hospital.get("address") or "정보 없음"),
                "latitude": latitude,
                "longitude": longitude,
            })

        self.hospitals = result
        return len(result)

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

        radius_m = float(radius_m)
        if not math.isfinite(radius_m) or radius_m <= 0:
            raise ValueError("반경은 0보다 큰 숫자여야 합니다.")

        self.radius_m = radius_m

    def clear_user_location(self):
        self.user_location = None
        self.radius_m = None

    def get_display_data(self):
        return {
            "hospitals": self.hospitals,
            "userLocation": self.user_location,
            "radiusM": self.radius_m,
        }

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
