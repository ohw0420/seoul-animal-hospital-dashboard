"""좌표 서비스 호환성과 실제 CSV 연결에서 발생했던 회귀를 검사한다."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from location_service import LocationService
from user_location import UserLocation
from src.dashboard_controller import DashboardController
from src.hospital_repository import HospitalRepository


def csv_bytes(x="209151.713940169", y="446519.612162961"):
    return (
        "관리번호,사업장명,영업상태명,도로명주소,전화번호,좌표정보(X),좌표정보(Y)\n"
        f"001,예시병원,영업/정상,서울특별시 송파구 올림픽로,02-001-0001,{x},{y}\n"
    ).encode("utf-8-sig")


class RepositoryCoordinateTests(unittest.TestCase):
    def test_existing_snake_case_service_keeps_output_contract(self):
        service = Mock(spec=["convert_coordinates"])
        service.convert_coordinates.return_value = (37.5, 127.0)
        repository = HospitalRepository(service)
        hospital = repository.load(csv_bytes())[0]
        service.convert_coordinates.assert_called_once_with(hospital.x, hospital.y)
        self.assertEqual(repository.get_all()[0]["lat"], 37.5)
        self.assertEqual(hospital.hospital_id, "001")
        self.assertEqual(hospital.phone, "02-001-0001")

    def test_team_camel_case_service_converts_actual_point(self):
        hospital = HospitalRepository(LocationService()).load(csv_bytes())[0]
        self.assertTrue(hospital.has_coordinates())
        self.assertAlmostEqual(hospital.latitude, 37.520865, places=4)
        self.assertAlmostEqual(hospital.longitude, 127.104313, places=4)

    def test_invalid_source_coordinates_are_kept_without_calling_service(self):
        for x, y in [("", "1"), ("bad", "1"), ("inf", "1"), ("-1", "1"), ("1", "0")]:
            with self.subTest(x=x, y=y):
                service = Mock(spec=["convertPoint"])
                hospital = HospitalRepository(service).load(csv_bytes(x, y))[0]
                service.convertPoint.assert_not_called()
                self.assertFalse(hospital.has_coordinates())
                self.assertIsNone(hospital.latitude)

    def test_invalid_conversion_result_becomes_missing_coordinates(self):
        for result in [None, (float("nan"), 127), (91, 127), (37, 181), (37,), ("bad", 127)]:
            with self.subTest(result=result):
                service = Mock(spec=["convertPoint"])
                service.convertPoint.return_value = result
                repository = HospitalRepository(service)
                hospital = repository.load(csv_bytes())[0]
                self.assertFalse(hospital.has_coordinates())
                json.dumps(repository.get_all(), allow_nan=False)

    def test_converter_failure_preserves_previous_data_and_report(self):
        service = Mock(spec=["convertPoint"])
        service.convertPoint.return_value = (37.5, 127)
        repository = HospitalRepository(service)
        previous = repository.load(csv_bytes())
        previous_report = repository.report.copy()
        service.convertPoint.side_effect = RuntimeError("변환 서비스 오류")
        with self.assertRaises(RuntimeError):
            repository.load(csv_bytes())
        self.assertEqual(repository.find_all(), previous)
        self.assertEqual(repository.report, previous_report)

    def test_loading_without_service_still_works(self):
        repository = HospitalRepository()
        hospital = repository.load(csv_bytes())[0]
        self.assertIsNone(hospital.latitude)
        self.assertIsNotNone(hospital.x)
        with self.assertRaisesRegex(ValueError, "convertPoint"):
            HospitalRepository(object())

    def test_real_csv_and_controller_nearby_without_external_address_api(self):
        class FixedAddressService(LocationService):
            def geocodeAddress(self, address):
                return 37.6194, 127.0598

        service = FixedAddressService()
        repository = HospitalRepository(service)
        hospitals = repository.load(
            Path(__file__).resolve().parents[1] / "data" / "seoul_animal_hospitals.csv"
        )
        self.assertEqual(len(hospitals), 2242)
        self.assertEqual(len(repository.find_by_district("마포구")), 121)
        self.assertEqual(sum(h.is_displayable() for h in hospitals), 995)
        self.assertEqual(sum(h.is_displayable() and h.has_coordinates() for h in hospitals), 983)
        controller = DashboardController(repository)
        nearby = controller.search_nearby("고정 좌표 테스트", 2, service, UserLocation())
        self.assertTrue(nearby)
        distances = [h["distance_km"] for h in nearby]
        self.assertEqual(distances, sorted(distances))
        self.assertTrue(all(d <= 2 for d in distances))
        self.assertTrue(all(h["status"] in ("영업", "휴업") for h in nearby))
        json.dumps(repository.get_all(), allow_nan=False)


if __name__ == "__main__":
    unittest.main()
