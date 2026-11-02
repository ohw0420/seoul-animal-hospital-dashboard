"""pandas로 서울시 CSV를 전처리하고 병원 객체 목록을 제공한다."""

import io
import math
import re
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

import pandas as pd

from .animal_hospital import AnimalHospital, NORMAL, SUSPENDED, CLOSED, OTHER
if TYPE_CHECKING:
    from .location_service import LocationService

SEOUL_DISTRICTS = tuple(sorted([
    "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
    "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
    "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구",
]))


class HospitalRepository:
    """원본 파일 처리는 내부에 모으고, 팀원에게는 병원 객체 목록을 전달한다."""

    REQUIRED = {"관리번호", "사업장명", "좌표정보(X)", "좌표정보(Y)"}

    def __init__(self, location_service: Optional["LocationService"] = None):
        if location_service is not None and not callable(
            getattr(location_service, "convert_coordinates", None)
        ):
            raise ValueError("위치 서비스에는 convert_coordinates(x, y) 메서드가 필요합니다.")
        self._location_service = location_service
        self._hospitals = []
        self.encoding = ""
        self.report = {}

    def validate(self, columns: list) -> None:
        missing = self.REQUIRED - set(columns)
        if missing:
            raise ValueError("CSV에 필요한 열이 없습니다: " + ", ".join(sorted(missing)))
        if not {"영업상태코드", "영업상태명"}.intersection(columns):
            raise ValueError("영업상태코드 또는 영업상태명 열이 필요합니다.")
        if not {"도로명주소", "지번주소"}.intersection(columns):
            raise ValueError("도로명주소 또는 지번주소 열이 필요합니다.")

    @staticmethod
    def normalize_status(code: str, name: str) -> str:
        code = code.strip()
        if code:
            # 식별 코드가 있으면 이름보다 우선하며, 미지원 코드를 정상으로 추정하지 않는다.
            return {"01": NORMAL, "1": NORMAL, "02": SUSPENDED,
                    "2": SUSPENDED, "03": CLOSED, "3": CLOSED}.get(code, OTHER)
        return {"영업/정상": NORMAL, "정상": NORMAL, "정상 영업": NORMAL,
                "휴업": SUSPENDED, "폐업": CLOSED}.get(name.strip(), OTHER)

    @staticmethod
    def extract_district(address: str) -> str:
        match = re.search(r"(?:서울특별시|서울시|서울)\s+([^\s]+구)(?:\s|$)", address)
        return match.group(1) if match and match.group(1) in SEOUL_DISTRICTS else "지역 미확인"

    def load(self, source: Union[bytes, str, Path]) -> list:
        """CSV 경로 또는 업로드된 bytes를 읽고 전처리한 병원 목록을 반환한다.

        전처리에 실패하면 기존 목록과 보고서는 유지한다.
        폐업 데이터도 보관하며, 지도 표시 여부는 AnimalHospital이 판단한다.
        """
        raw = source if isinstance(source, bytes) else Path(source).read_bytes()
        dataframe, encoding = self._read_dataframe(raw)
        self.validate(dataframe.columns.tolist())

        # 1. 열 개수가 부족한 행을 구분하고, 문자열 앞뒤 공백을 정리한다.
        # 빈 셀("")과 CSV 행 자체에 필드가 없는 경우(None)는 다르게 취급한다.
        total = len(dataframe)
        malformed = dataframe.isna().any(axis=1)
        dataframe = dataframe.fillna("").apply(lambda column: column.str.strip())

        # 2. 병원 식별에 필요한 관리번호·병원명이 비어 있는 행을 제외한다.
        invalid_mask = malformed | dataframe["관리번호"].eq("") | dataframe["사업장명"].eq("")
        invalid = int(invalid_mask.sum())
        dataframe = dataframe.loc[~invalid_mask].copy()

        # 3. 관리번호가 같은 경우 원본에서 먼저 나온 행을 유지한다.
        duplicates = int(dataframe.duplicated(subset=["관리번호"]).sum())
        dataframe = dataframe.drop_duplicates(subset=["관리번호"], keep="first").copy()
        if dataframe.empty:
            raise ValueError("읽을 수 있는 병원 데이터가 없습니다.")

        # 4. 생략 가능한 열은 빈 문자열로 채우고 상태·주소·자치구를 통일한다.
        for column in ("영업상태코드", "영업상태명", "도로명주소", "지번주소", "전화번호"):
            if column not in dataframe.columns:
                dataframe[column] = ""
        dataframe["status"] = dataframe.apply(
            lambda row: self.normalize_status(row["영업상태코드"], row["영업상태명"]), axis=1
        )
        dataframe["address"] = dataframe["도로명주소"].where(
            dataframe["도로명주소"].ne(""), dataframe["지번주소"]
        )
        road_district = dataframe["도로명주소"].map(self.extract_district)
        lot_district = dataframe["지번주소"].map(self.extract_district)
        dataframe["district"] = road_district.where(road_district.ne("지역 미확인"), lot_district)

        # 5. 식별번호·전화번호는 문자열을 유지하고 좌표 열만 숫자로 바꾼다.
        # 숫자로 바꿀 수 없는 좌표는 NaN이 되며, 변환 서비스는 None을 반환한다.
        dataframe["좌표정보(X)"] = pd.to_numeric(dataframe["좌표정보(X)"], errors="coerce")
        dataframe["좌표정보(Y)"] = pd.to_numeric(dataframe["좌표정보(Y)"], errors="coerce")
        if self._location_service is not None:
            dataframe["coordinates"] = dataframe.apply(
                lambda row: self._location_service.convert_coordinates(
                    row["좌표정보(X)"], row["좌표정보(Y)"]
                ), axis=1
            )
        else:
            # 팀원의 변환 서비스가 준비되기 전에도 전처리·조회는 가능하다.
            # 원본 X/Y를 위경도로 오인하지 않도록 지도 좌표는 비워둔다.
            dataframe["coordinates"] = None

        # 6. 지도·컨트롤러 담당자는 DataFrame 대신 기존 병원 객체를 사용한다.
        hospitals = []
        for row in dataframe.to_dict(orient="records"):
            coordinates = row["coordinates"]
            hospitals.append(AnimalHospital(
                hospital_id=row["관리번호"], name=row["사업장명"], status=row["status"],
                phone=row["전화번호"], address=row["address"], district=row["district"],
                latitude=coordinates[0] if coordinates else None,
                longitude=coordinates[1] if coordinates else None,
                x=float(row["좌표정보(X)"]) if math.isfinite(row["좌표정보(X)"]) else None,
                y=float(row["좌표정보(Y)"]) if math.isfinite(row["좌표정보(Y)"]) else None,
            ))

        self._hospitals = hospitals
        self.encoding = encoding
        self.report = {"원본 행 수": total, "정상 로딩": len(hospitals),
                       "중복 관리번호 제외": duplicates, "필수값 누락·형식 오류 제외": invalid,
                       **dataframe["status"].value_counts().to_dict()}
        return self.find_all()

    def _read_dataframe(self, raw: bytes) -> tuple:
        """식별번호·전화번호의 앞자리 0과 'NA' 같은 실제 문자열을 보존한다."""
        for encoding in ("utf-8-sig", "cp949", "euc-kr"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("CSV 인코딩을 읽을 수 없습니다. UTF-8 또는 CP949 파일을 사용해 주세요.")
        try:
            dataframe = pd.read_csv(
                io.StringIO(text), dtype=str, keep_default_na=False,
                engine="python", on_bad_lines="error",
            )
        except pd.errors.EmptyDataError:
            raise ValueError("CSV 파일이 비어 있습니다.") from None
        except pd.errors.ParserError:
            raise ValueError("CSV의 따옴표 또는 열 개수가 올바르지 않습니다. 원본 파일을 확인해 주세요.") from None
        # 첫 행부터 열이 많으면 pandas가 일부 값을 인덱스로 오인할 수 있다.
        if not isinstance(dataframe.index, pd.RangeIndex):
            raise ValueError("CSV의 열 개수가 올바르지 않습니다. 원본 파일을 확인해 주세요.")
        dataframe.columns = dataframe.columns.str.strip()
        if dataframe.columns.duplicated().any():
            raise ValueError("공백을 제거한 뒤 중복되는 열 이름이 있습니다.")
        return dataframe, encoding

    def find_all(self) -> list:
        """전체 병원 목록의 사본을 반환한다. 폐업·기타 상태도 포함한다."""
        return list(self._hospitals)

    def find_by_district(self, district: str = "서울 전체") -> list:
        """팀원과 합의한 조회 방식: 자치구 이름을 받아 병원 객체 목록 반환."""
        return [h for h in self._hospitals if district == "서울 전체" or h.district == district]

    def get_all(self) -> list:
        """현재 GitHub 컨트롤러용 딕셔너리 목록. 폐업·기타 상태도 포함한다.

        객체 목록이 필요한 팀원은 find_all()/find_by_district()를 사용한다.
        위도·경도가 필요하면 생성 시 위치 서비스를 전달한 뒤 load()한다.
        """
        return [hospital.to_dict() for hospital in self._hospitals]
