"""병원 한 곳을 표현하는 모델."""

from dataclasses import dataclass
from typing import Optional
import math

NORMAL = "정상 영업"
SUSPENDED = "휴업"
CLOSED = "폐업"
OTHER = "기타 상태"


@dataclass(frozen=True)
class AnimalHospital:
    """전처리된 병원 한 곳의 정보. 생성 뒤에는 속성을 다시 대입하지 않는다."""

    hospital_id: str
    name: str
    status: str
    phone: str
    address: str
    district: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None

    def is_closed(self) -> bool:
        """폐업만 판별한다. 지도 표시 판단에는 is_displayable()을 사용한다."""
        return self.status == CLOSED

    def is_displayable(self) -> bool:
        """정상·휴업만 허용한다. 말소 등 기타 상태도 제외한다."""
        return self.status in (NORMAL, SUSPENDED)

    def has_coordinates(self) -> bool:
        """누락값·무한대·위경도 범위 오류가 없는지 확인한다."""
        return (
            self.latitude is not None and self.longitude is not None
            and math.isfinite(self.latitude) and math.isfinite(self.longitude)
            and -90 <= self.latitude <= 90 and -180 <= self.longitude <= 180
        )

    def get_display_info(self) -> dict:
        """지도 말풍선용 정보를 반환한다. 원본 속성은 바꾸지 않는다."""
        return {
            "병원명": self.name,
            "영업상태": self.status,
            "전화번호": self.phone or "정보 없음",
            "주소": self.address or "정보 없음",
        }

    def to_dict(self) -> dict:
        """현재 팀 컨트롤러·JSON 전달용 형식. 객체 내부의 상태는 변경하지 않는다.

        컨트롤러의 정상 상태 비교값은 '영업'이므로 반환할 때만 변환한다.
        status_label에는 기존 화면용 상태명('정상 영업' 등)을 그대로 담는다.
        x/y는 원본 좌표이며, lat/lng는 변환 완료된 위도·경도다.
        """
        return {
            "id": self.hospital_id,
            "name": self.name,
            "status": "영업" if self.status == NORMAL else self.status,
            "status_label": self.status,
            "phone": self.phone,
            "address": self.address,
            "gu": self.district,
            "lat": self.latitude,
            "lng": self.longitude,
            "x": self.x,
            "y": self.y,
        }
