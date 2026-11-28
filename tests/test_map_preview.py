import json
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from location_service import LocationService
from src.hospital_repository import HospitalRepository
from map_preview import MapPreview, create_server


class FixedAddressService(LocationService):
    """외부 주소 API만 고정하고 실제 팀원 좌표 변환·거리 계산은 사용합니다."""
    def geocodeAddress(self, address):
        return None if address == '없는주소' else (37.6194, 127.0598)


class MapPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = FixedAddressService()
        cls.repository = HospitalRepository(cls.service)
        cls.repository.load(Path(__file__).resolve().parents[1] / 'data/seoul_animal_hospitals.csv')
        cls.preview = MapPreview(cls.repository, cls.service)

    def test_real_districts_include_normal_and_suspended(self):
        initial = self.preview.district()
        self.assertEqual(len(initial['districts']), 25)
        self.assertEqual(sum(d['count'] for d in initial['districts']), 985)
        records = [h for d in initial['districts'] for h in self.preview.district(d['name'])['hospitals']]
        self.assertEqual(len(records), 983)
        self.assertEqual({h['status'] for h in records}, {'정상영업', '휴업'})
        json.dumps(records, allow_nan=False)

    def test_nearby_connects_user_radius_and_real_results(self):
        data = self.preview.nearby({'address':'고정 좌표 검사', 'radiusM':2000})
        self.assertEqual(data['viewMode'], 'nearby')
        self.assertEqual(data['radiusM'], 2000)
        self.assertEqual(data['userLocation']['latitude'], 37.6194)
        self.assertTrue(data['hospitals'])
        self.assertLess(len(data['hospitals']), 983)

    def test_invalid_input_and_missing_address(self):
        for radius in (0, -1, True, None, '잘못된값', float('nan'), 500, 1250, 5500):
            with self.assertRaises(ValueError): self.preview.nearby({'address':'시청','radiusM':radius})
        with self.assertRaises(ValueError): self.preview.nearby({'address':'','radiusM':1000})
        with self.assertRaises(ValueError): self.preview.nearby({'address':'없는주소','radiusM':1000})
        with self.assertRaises(ValueError): self.preview.district('없는구')

    def test_server_html_assets_and_search_routes(self):
        server = create_server(self.preview, 'TEST_ONLY', 0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            html = opener.open(base).read().decode('utf-8')
            self.assertIn('/static/map_controls.js', html)
            self.assertIn('id="source-label"', html)
            self.assertIn('효자동물병원', html)
            initial = json.loads(html.split('window.MAP_INITIAL_DATA = ', 1)[1].split(';</script>', 1)[0])
            self.assertEqual(len(initial['hospitals']), 983)
            self.assertTrue(all(h['district'] in {d['name'] for d in initial['districts']} for h in initial['hospitals']))
            self.assertNotIn('__MAP_PAYLOAD__', html)
            for asset in ('hospital_map.js','map_controls.js','seoul_districts.geojson'):
                self.assertEqual(opener.open(base+'/static/'+asset).status, 200)
            district = json.load(opener.open(base+'/api/district?name='+quote('마포구')))
            self.assertEqual(len(district['hospitals']), 51)
            request = urllib.request.Request(base+'/api/nearby',
                data=json.dumps({'address':'고정좌표','radiusM':2000}).encode(),
                headers={'Content-Type':'application/json'}, method='POST')
            data = json.load(opener.open(request))
            self.assertTrue(data['hospitals'])
            self.assertEqual(data['viewMode'], 'nearby')
            with self.assertRaises(urllib.error.HTTPError) as result: opener.open(base+'/.env')
            self.assertEqual(result.exception.code, 404)
            bad = urllib.request.Request(base+'/api/nearby', data=b'{broken',method='POST')
            with self.assertRaises(urllib.error.HTTPError) as result: opener.open(bad)
            self.assertEqual(result.exception.code, 400)
        finally:
            server.shutdown();server.server_close();worker.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
