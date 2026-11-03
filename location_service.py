"""
서울시 동물병원 지도 - 위치 관련 클래스 (담당: 정부성)

- UserLocation    : 사용자가 설정한 본인 위치(주소, 위도, 경도) 관리
- LocationService : 주소 -> 위도·경도 변환(지오코딩), 병원 좌표(TM) -> 위도·경도 변환,
                    사용자 위치 기준 거리 계산 / 반경 내 병원 검색

필요 패키지: pandas, numpy, requests  (pyproj가 설치돼 있으면 좌표 변환에 자동 사용)
"""

import os
import math

import numpy as np
import pandas as pd
import requests

try:                      # pyproj가 있으면 사용하고, 없으면 직접 구현한 변환식을 사용
    from pyproj import Transformer
except ImportError:
    Transformer = None


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
# LocationService
# ============================================================
class LocationService:
    """주소를 지도 좌표로 변환하고, 병원 좌표 형식을 위도·경도로 변환하는 클래스"""

    KAKAO_URL = "https://dapi.kakao.com/v2/local/search/address.json"
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    EARTH_RADIUS_KM = 6371.0088

    def __init__(self, api_key=None, provider=None, source_crs="EPSG:5174", timeout=5):
        """
        api_key    : 카카오 REST API 키 (없으면 환경변수 KAKAO_API_KEY 사용)
        provider   : "kakao" 또는 "nominatim" (지정 안 하면 키가 있을 때 kakao, 없으면 nominatim)
        source_crs : 병원 데이터 좌표계. 서울시 인허가 데이터의 좌표정보(X,Y)는
                     중부원점 TM(Bessel) = EPSG:5174
        """
        self.__api_key = api_key or os.environ.get("KAKAO_API_KEY")
        self.__provider = provider or ("kakao" if self.__api_key else "nominatim")
        self.__source_crs = source_crs
        self.__timeout = timeout
        self.__cache = {}          # 같은 주소를 여러 번 검색하지 않도록 캐시

        self.__transformer = None
        if Transformer is not None:
            self.__transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
        elif source_crs != "EPSG:5174":
            raise ValueError("pyproj 없이 지원하는 좌표계는 EPSG:5174뿐입니다. pip install pyproj")

    @property
    def provider(self):
        return self.__provider

    @property
    def sourceCrs(self):
        return self.__source_crs

    # --------------------------------------------------------
    # 1) 주소 -> 위도·경도 (지오코딩)
    # --------------------------------------------------------
    def geocodeAddress(self, address):
        """주소를 (위도, 경도)로 변환. 찾지 못하면 None 반환"""
        address = (address or "").strip()
        if not address:
            raise ValueError("주소를 입력하세요.")
        if address in self.__cache:
            return self.__cache[address]

        try:
            if self.__provider == "kakao":
                result = self.__geocodeKakao(address)
            else:
                result = self.__geocodeNominatim(address)
        except requests.RequestException as e:
            print(f"[LocationService] 주소 검색 실패: {e}")
            return None

        if result is not None:
            self.__cache[address] = result
        return result

    def __geocodeKakao(self, address):
        if not self.__api_key:
            raise ValueError("카카오 API 키가 필요합니다.")
        res = requests.get(
            self.KAKAO_URL,
            headers={"Authorization": f"KakaoAK {self.__api_key}"},
            params={"query": address},
            timeout=self.__timeout,
        )
        res.raise_for_status()
        docs = res.json().get("documents", [])
        if not docs:
            return None
        return (float(docs[0]["y"]), float(docs[0]["x"]))   # 카카오: x=경도, y=위도

    def __geocodeNominatim(self, address):
        query = address if "서울" in address else f"서울특별시 {address}"
        res = requests.get(
            self.NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "kr"},
            headers={"User-Agent": "seoul-animal-hospital-dashboard"},
            timeout=self.__timeout,
        )
        res.raise_for_status()
        data = res.json()
        if not data:
            return None
        return (float(data[0]["lat"]), float(data[0]["lon"]))

    def setUserLocation(self, user_location, address):
        """주소를 변환해 UserLocation에 저장. 성공하면 True"""
        coords = self.geocodeAddress(address)
        if coords is None:
            return False
        user_location.setLocation(address, *coords)
        return True

    # --------------------------------------------------------
    # 2) 병원 좌표(TM) -> 위도·경도
    # --------------------------------------------------------
    def convertCoordinates(self, df, x_col="좌표정보(X)", y_col="좌표정보(Y)",
                           lat_col="위도", lon_col="경도", dropna=True):
        """
        병원 DataFrame의 TM 좌표를 위도·경도 컬럼으로 변환해 새 DataFrame 반환.
        좌표가 비어 있거나 숫자가 아닌 행은 dropna=True면 제거.
        """
        result = df.copy()
        x = pd.to_numeric(result[x_col], errors="coerce")
        y = pd.to_numeric(result[y_col], errors="coerce")
        valid = x.notna() & y.notna() & (x > 0) & (y > 0)

        lon = pd.Series(np.nan, index=result.index)
        lat = pd.Series(np.nan, index=result.index)
        if valid.any():
            lo, la = self.__tmToWgs84(x[valid].to_numpy(), y[valid].to_numpy())
            lon[valid] = lo
            lat[valid] = la

        result[lat_col] = lat
        result[lon_col] = lon
        if dropna:
            result = result.dropna(subset=[lat_col, lon_col])
        return result

    def convertPoint(self, x, y):
        """좌표 하나 변환 -> (위도, 경도). AnimalHospital 객체 하나에 쓸 때"""
        lon, lat = self.__tmToWgs84(np.array([float(x)]), np.array([float(y)]))
        return (float(lat[0]), float(lon[0]))

    def __tmToWgs84(self, x, y):
        if self.__transformer is not None:
            return self.__transformer.transform(x, y)
        return _epsg5174_to_wgs84(x, y)

    # --------------------------------------------------------
    # 3) 거리 계산 / 반경 내 병원 검색 (내 주변 병원 검색 화면용)
    # --------------------------------------------------------
    def calculateDistance(self, df, user_location, lat_col="위도", lon_col="경도",
                          dist_col="거리(km)"):
        """사용자 위치에서 각 병원까지의 거리(km) 컬럼 추가 (하버사인 공식)"""
        if not user_location.hasLocation():
            raise ValueError("사용자 위치가 설정되지 않았습니다.")
        ulat, ulon = user_location.getCoordinates()

        lat1, lon1 = math.radians(ulat), math.radians(ulon)
        lat2 = np.radians(df[lat_col].to_numpy(dtype=float))
        lon2 = np.radians(df[lon_col].to_numpy(dtype=float))
        a = (np.sin((lat2 - lat1) / 2) ** 2
             + math.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)

        result = df.copy()
        result[dist_col] = 2 * self.EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))
        return result

    def findNearby(self, df, user_location, radius_km=1.0, dist_col="거리(km)", **kwargs):
        """반경 radius_km 안의 병원만 가까운 순으로 반환"""
        result = self.calculateDistance(df, user_location, dist_col=dist_col, **kwargs)
        return result[result[dist_col] <= radius_km].sort_values(dist_col)


# ============================================================
# pyproj가 없을 때 쓰는 EPSG:5174 -> WGS84 변환 (numpy 벡터 연산)
#   1) 횡메르카토르 역변환 (Bessel 1841 타원체)
#   2) Bessel -> WGS84 7-파라미터 Helmert 변환 (EPSG:5174 towgs84 값)
# ============================================================
_BESSEL_A, _BESSEL_INVF = 6377397.155, 299.1528128
_WGS_A, _WGS_INVF = 6378137.0, 298.257223563
_TM = dict(lat0=38.0, lon0=127.0028902777778, k0=1.0, x0=200000.0, y0=500000.0)
_TOWGS84 = (-115.80, 474.99, 674.11, 1.16, -2.31, -1.63, 6.43)  # m, m, m, ″, ″, ″, ppm


def _meridian_arc(phi, a, e2):
    e4, e6 = e2 * e2, e2 ** 3
    return a * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi
                - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * np.sin(2 * phi)
                + (15 * e4 / 256 + 45 * e6 / 1024) * np.sin(4 * phi)
                - (35 * e6 / 3072) * np.sin(6 * phi))


def _tm_inverse(x, y):
    a = _BESSEL_A
    f = 1 / _BESSEL_INVF
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    k0 = _TM["k0"]
    phi0, lam0 = np.radians(_TM["lat0"]), np.radians(_TM["lon0"])

    M = _meridian_arc(phi0, a, e2) + (y - _TM["y0"]) / k0
    mu = M / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - np.sqrt(1 - e2)) / (1 + np.sqrt(1 - e2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * np.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * np.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * np.sin(6 * mu)
            + (1097 * e1 ** 4 / 512) * np.sin(8 * mu))

    s, c, t = np.sin(phi1), np.cos(phi1), np.tan(phi1)
    C1, T1 = ep2 * c ** 2, t ** 2
    N1 = a / np.sqrt(1 - e2 * s ** 2)
    R1 = a * (1 - e2) / (1 - e2 * s ** 2) ** 1.5
    D = (x - _TM["x0"]) / (N1 * k0)

    phi = phi1 - (N1 * t / R1) * (
        D ** 2 / 2
        - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * ep2) * D ** 4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 252 * ep2 - 3 * C1 ** 2) * D ** 6 / 720)
    lam = lam0 + (D - (1 + 2 * T1 + C1) * D ** 3 / 6
                  + (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * ep2 + 24 * T1 ** 2) * D ** 5 / 120) / c
    return phi, lam


def _geodetic_to_ecef(phi, lam, a, invf):
    f = 1 / invf
    e2 = f * (2 - f)
    N = a / np.sqrt(1 - e2 * np.sin(phi) ** 2)
    return (N * np.cos(phi) * np.cos(lam), N * np.cos(phi) * np.sin(lam),
            N * (1 - e2) * np.sin(phi))


def _ecef_to_geodetic(X, Y, Z, a, invf):
    f = 1 / invf
    e2 = f * (2 - f)
    b = a * (1 - f)
    ep2 = (a ** 2 - b ** 2) / b ** 2
    p = np.sqrt(X ** 2 + Y ** 2)
    th = np.arctan2(Z * a, p * b)
    phi = np.arctan2(Z + ep2 * b * np.sin(th) ** 3, p - e2 * a * np.cos(th) ** 3)
    return phi, np.arctan2(Y, X)


def _epsg5174_to_wgs84(x, y):
    """x, y(numpy 배열) -> (경도 배열, 위도 배열)"""
    phi, lam = _tm_inverse(np.asarray(x, float), np.asarray(y, float))
    X, Y, Z = _geodetic_to_ecef(phi, lam, _BESSEL_A, _BESSEL_INVF)

    dx, dy, dz, rx, ry, rz, ds = _TOWGS84
    sec = np.pi / (180 * 3600)
    rx, ry, rz, m = rx * sec, ry * sec, rz * sec, 1 + ds * 1e-6
    # Position Vector 회전 규약 (PROJ towgs84와 동일)
    X2 = dx + m * (X - rz * Y + ry * Z)
    Y2 = dy + m * (rz * X + Y - rx * Z)
    Z2 = dz + m * (-ry * X + rx * Y + Z)

    phi_w, lam_w = _ecef_to_geodetic(X2, Y2, Z2, _WGS_A, _WGS_INVF)
    return np.degrees(lam_w), np.degrees(phi_w)


# ============================================================
# 사용 예시
# ============================================================
if __name__ == "__main__":
    # 실제로는 HospitalRepository가 읽은 데이터 사용
    # df = pd.read_csv("서울시 동물병원 인허가 정보.csv", encoding="cp949")
    df = pd.DataFrame({
        "사업장명": ["A동물병원", "B동물병원", "C동물병원", "좌표없는병원"],
        "영업상태명": ["영업/정상", "휴업", "영업/정상", "영업/정상"],
        "좌표정보(X)": [198000.0, 199500.0, 205000.0, None],
        "좌표정보(Y)": [451900.0, 452300.0, 446000.0, None],
    })

    service = LocationService()                # KAKAO_API_KEY 환경변수 있으면 카카오 사용
    hospitals = service.convertCoordinates(df)
    print(hospitals[["사업장명", "위도", "경도"]], "\n")

    user = UserLocation()
    if not service.setUserLocation(user, "서울특별시 중구 세종대로 110"):
        user.setLocation("서울시청(직접 입력)", 37.5665, 126.9780)   # 주소 검색 실패 시
    print(user, "\n")

    print(service.findNearby(hospitals, user, radius_km=2)[["사업장명", "영업상태명", "거리(km)"]])
    user.clearLocation()
    print("\n초기화 후:", user)
