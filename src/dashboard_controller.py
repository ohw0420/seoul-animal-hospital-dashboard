"""
DashboardController
- 지도 화면(대시보드)에 필요한 데이터를 모아서 넘겨주는 클래스
- 데이터 담당 클래스(get_all() 메서드 필요)를 받아서 사용
"""
import pandas as pd

class DashboardController:
    def __init__(self, repository):
        """
        repository: 팀원이 만든 데이터 클래스 (get_all() 메서드가 있어야 함)
        """
        self.repository = repository

    def get_hospitals(self, only_open=False):
        """병원 목록 반환. only_open=True면 영업 중인 곳만"""
        hospitals = self.repository.get_all()

        if only_open:
            return [h for h in hospitals if h["status"] == "영업"]
        return hospitals

    def get_district_counts(self):
        """구별 병원 수 반환. 예: {"강남구": 2, "마포구": 1}"""
        counts = {}
        for h in self.get_hospitals(only_open=True):
            counts[h["gu"]] = counts.get(h["gu"], 0) + 1
        return counts

    def search(self, keyword):
        """병원 이름 또는 주소에 keyword가 들어간 병원 반환"""
        return [
            h for h in self.get_hospitals()
            if keyword in h["name"] or keyword in h["address"]
        ]

    def get_dashboard_data(self):
        """지도 페이지에 한 번에 넘겨줄 데이터"""
        return {
            "hospitals": self.get_hospitals(only_open=True),
            "district_counts": self.get_district_counts(),
        }

    def search_nearby(self, address, radius_km, location_service, user_location):
        """주소 기준 반경 radius_km 안의 병원(정상·휴업)을 가까운 순으로 반환"""
        if not location_service.setUserLocation(user_location, address):
            raise ValueError(f"주소를 찾을 수 없습니다: {address}")

        hospitals = [h for h in self.get_hospitals() if h["status"] in ("영업", "휴업")]
        df = pd.DataFrame({"위도": [h["lat"] for h in hospitals],
                           "경도": [h["lng"] for h in hospitals]})
        nearby = location_service.findNearby(df, user_location, radius_km)

        return [{**hospitals[i], "distance_km": round(d, 3)}
                for i, d in nearby["거리(km)"].items()]
    
