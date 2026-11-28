import unittest
from src.animal_hospital import AnimalHospital, NORMAL
from src.hospital_map_view import HospitalMapView


class MapViewTests(unittest.TestCase):
    def setUp(self):
        self.view = HospitalMapView()
        self.row = dict(name='병원', status='영업', phone=None, address='', lat=37.56, lng=126.98)

    def test_team_object_and_dictionary(self):
        obj = AnimalHospital('id', '객체 병원', NORMAL, '', '', '중구', 37.56, 126.98)
        self.assertEqual(self.view.render_hospitals([self.row, obj]), 2)
        self.assertEqual(self.view.hospitals[1]['status'], '정상영업')
        self.assertEqual(self.view.hospitals[1]['district'], '중구')
        self.view.render_hospitals([dict(self.row, district='마포구')])
        self.assertEqual(self.view.hospitals[0]['district'], '마포구')
        self.assertEqual(self.view.hospitals[0]['phone'], '정보 없음')

    def test_bad_rows_and_replace(self):
        self.assertEqual(self.view.render_hospitals([self.row, None, {},
            dict(self.row, status='폐업'), dict(self.row, lat=float('nan')),
            dict(self.row, lat=True), dict(self.row, lng=200)]), 1)
        self.assertEqual(self.view.render_hospitals([]), 0)
        self.assertEqual(self.view.hospitals, [])

    def test_radius_and_reset(self):
        with self.assertRaises(ValueError): self.view.show_search_radius(1000)
        self.view.show_user_location(37.56, 126.98)
        for radius in (0, -1, float('inf'), float('nan'), True):
            with self.assertRaises(ValueError): self.view.show_search_radius(radius)
        self.view.show_search_radius(1000)
        self.view.clear_user_location()
        self.assertIsNone(self.view.radius_m)

    def test_district_validation_and_snapshot(self):
        district = dict(name='중구', count=2, latitude=37.56, longitude=126.98)
        self.assertEqual(self.view.render_districts([district, dict(district, count=-1), dict(district, count=True)]), 1)
        data = self.view.get_display_data()
        data['districts'][0]['count'] = 999
        self.assertEqual(self.view.districts[0]['count'], 2)

    def test_json_escaping_and_template(self):
        self.view.render_hospitals([dict(self.row, name='</script><script>alert(1)</script>')])
        html = self.view.render_html('TEST_ONLY')
        self.assertNotIn('__MAP_PAYLOAD__', html)
        self.assertNotIn('</script><script>alert', html)
        self.assertIn('\\u003c/script>', html)
        self.assertIn('/static/hospital_map.js', html)

    def test_counts_connect_all_25_districts_without_recounting(self):
        self.assertEqual(self.view.render_district_counts({'노원구': 3, '마포구': 1}), 25)
        by_name = {d['name']: d for d in self.view.districts}
        self.assertEqual(by_name['노원구']['count'], 3)
        self.assertEqual(by_name['중구']['count'], 0)
        self.assertEqual(sum(d['count'] for d in self.view.districts), 4)
        for bad in ({'없는구': 1}, {'중구': -1}, {'중구': True}, {'중구': 1.5}):
            with self.assertRaises(ValueError): self.view.render_district_counts(bad)
        self.assertEqual(sum(d['count'] for d in self.view.districts), 4)


if __name__ == '__main__':
    unittest.main()
