"""실제 CSV 전처리와 주변 병원 조회 예시. 프로젝트 최상위에서 모듈로 실행한다."""

import argparse
import json
from pathlib import Path

import pandas as pd

from location_service import LocationService
from user_location import UserLocation
from src.dashboard_controller import DashboardController
from src.hospital_repository import HospitalRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", default="마포구")
    parser.add_argument("--latitude", type=float, default=37.6194)
    parser.add_argument("--longitude", type=float, default=127.0598)
    parser.add_argument("--radius-km", type=float, default=2.0)
    args = parser.parse_args()
    if not 0 < args.radius_km < float("inf"):
        parser.error("반경은 0보다 큰 유한한 숫자여야 합니다.")

    service = LocationService()
    repository = HospitalRepository(service)
    source = Path(__file__).resolve().parents[1] / "data" / "seoul_animal_hospitals.csv"
    hospitals = repository.load(source)
    controller = DashboardController(repository)

    # 주소 검색 API 없이 두 클래스와 팀원의 거리 계산 코드를 확인한다.
    user = UserLocation()
    user.setLocation("실행 옵션으로 지정한 위치", args.latitude, args.longitude)
    candidates = [h for h in hospitals if h.is_displayable() and h.has_coordinates()]
    frame = pd.DataFrame({
        "위도": [h.latitude for h in candidates],
        "경도": [h.longitude for h in candidates],
    })
    nearby = service.findNearby(frame, user, args.radius_km)
    nearby_records = [
        {**candidates[index].to_dict(), "distance_km": round(distance, 3)}
        for index, distance in nearby["거리(km)"].items()
    ]

    print(json.dumps({
        "전처리 결과": repository.report,
        "선택 지역": args.district,
        "지역 병원 수_모든 상태": len(repository.find_by_district(args.district)),
        "정상 또는 휴업": sum(h.is_displayable() for h in hospitals),
        "지도 표시 가능_상태와 좌표 확인": len(candidates),
        "컨트롤러 정상 영업 수": len(controller.get_hospitals(only_open=True)),
        "검색 반경_km": args.radius_km,
        "반경 내 병원 수": len(nearby_records),
        "가까운 병원_최대3개": nearby_records[:3],
    }, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
