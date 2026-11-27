"""
서울시 동물병원 지도 - UserLocation 클래스 (담당: 정부성)

사용자가 설정한 본인 위치(주소, 위도, 경도)를 저장·관리한다.
"""


# ============================================================
# UserLocation
# ============================================================
class UserLocation:
    """사용자가 입력한 주소와 변환된 좌표를 저장하는 클래스"""

    # 서울 및 인근의 대략적인 범위 (잘못 변환된 좌표 걸러내기용)
    LAT_RANGE = (37.0, 38.0)
    LON_RANGE = (126.5, 127.5)

    def __init__(self):
        self.__address = None
        self.__latitude = None
        self.__longitude = None

    # ---- 읽기 전용 속성 (캡슐화) ----
    @property
    def address(self):
        return self.__address

    @property
    def latitude(self):
        return self.__latitude

    @property
    def longitude(self):
        return self.__longitude

    # ---- 주요 메서드 ----
    def setLocation(self, address, latitude, longitude):
        """위치 설정. 다른 주소를 입력하면 새 위치로 갱신된다."""
        latitude, longitude = float(latitude), float(longitude)
        if not (self.LAT_RANGE[0] <= latitude <= self.LAT_RANGE[1]
                and self.LON_RANGE[0] <= longitude <= self.LON_RANGE[1]):
            raise ValueError(f"서울 지역 좌표가 아닙니다: ({latitude}, {longitude})")
        self.__address = address
        self.__latitude = latitude
        self.__longitude = longitude

    def clearLocation(self):
        """위치 초기화"""
        self.__address = None
        self.__latitude = None
        self.__longitude = None

    def hasLocation(self):
        return self.__latitude is not None and self.__longitude is not None

    def getCoordinates(self):
        """(위도, 경도) 반환 - 지도(folium 등)에 바로 넣을 수 있는 형식"""
        if not self.hasLocation():
            return None
        return (self.__latitude, self.__longitude)

    def toDict(self):
        return {"주소": self.__address, "위도": self.__latitude, "경도": self.__longitude}

    def __str__(self):
        if not self.hasLocation():
            return "UserLocation(위치 미설정)"
        return f"UserLocation({self.__address}, {self.__latitude:.6f}, {self.__longitude:.6f})"


# ============================================================
# 사용 예시
# ============================================================
if __name__ == "__main__":
    user = UserLocation()
    print(user)
    user.setLocation("서울특별시 중구 세종대로 110", 37.5665, 126.9780)
    print(user, user.getCoordinates())
    try:
        user.setLocation("부산", 35.18, 129.07)
    except ValueError as e:
        print("검증:", e)
    user.clearLocation()
    print("초기화 후:", user)
