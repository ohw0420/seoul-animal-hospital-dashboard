"""지도 담당 통합 시연. 팀원 클래스를 호출하며 원본 CSV·좌표·검색 로직은 구현하지 않는다."""
import argparse
import json
import math
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from location_service import LocationService
from user_location import UserLocation
from src.dashboard_controller import DashboardController
from src.hospital_repository import HospitalRepository
from src.hospital_map_view import HospitalMapView

ROOT = Path(__file__).resolve().parent


class MapPreview:
    """지도 입출력 연결용 시연 어댑터. 팀원의 컨트롤러를 대체하지 않는다."""

    def __init__(self, repository, location_service):
        self.repository = repository
        self.service = location_service
        self.controller = DashboardController(repository)
        summary = HospitalMapView()
        summary.render_district_counts(self.controller.get_district_counts())
        self.districts = summary.get_display_data()['districts']
        self.names = {d['name'] for d in self.districts}

    def _view(self):
        view = HospitalMapView()
        view.render_districts(self.districts)
        return view

    def district(self, name=''):
        if name and name not in self.names:
            raise ValueError('서울 자치구를 선택하세요.')
        view = self._view()
        if name:
            view.render_hospitals(self.repository.find_by_district(name))
        return {
            **view.get_display_data(),
            'selectedDistrict': name or None,
            'viewMode': 'district' if name else 'overview',
            'label': name,
        }

    def nearby(self, data):
        address = data.get('address')
        if not isinstance(address, str) or not address.strip():
            raise ValueError('검색할 주소를 입력하세요.')
        if len(address) > 300:
            raise ValueError('주소는 300자 이내로 입력하세요.')
        value = data.get('radiusM')
        if isinstance(value, bool):
            raise ValueError('반경은 0보다 큰 숫자여야 합니다.')
        try:
            radius = float(value)
        except (TypeError, ValueError, OverflowError):
            raise ValueError('반경은 0보다 큰 숫자여야 합니다.') from None
        if not math.isfinite(radius) or not 1000 <= radius <= 5000 or radius % 500 != 0:
            raise ValueError('반경은 1~5km 범위에서 0.5km 단위로 선택하세요.')
        user = UserLocation()
        # km 변환과 결과 표시만 연결합니다. 거리·검색은 기존 팀원 코드에서 수행합니다.
        hospitals = self.controller.search_nearby(address.strip(), radius / 1000, self.service, user)
        view = self._view()
        view.render_hospitals(hospitals)
        view.show_user_location(user.latitude, user.longitude)
        view.show_search_radius(radius)
        return {
            **view.get_display_data(),
            'selectedDistrict': None,
            'viewMode': 'nearby',
            'label': f'내 주변 {radius / 1000:g}km',
        }


def create_server(preview, javascript_key, port=8000):
    files = {
        '/static/hospital_map.js': ('static/hospital_map.js', 'text/javascript'),
        '/static/map_controls.js': ('static/map_controls.js', 'text/javascript'),
        '/static/seoul_districts.geojson': ('static/seoul_districts.geojson', 'application/geo+json'),
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # 사용자 주소와 요청 내용은 터미널에 기록하지 않습니다.

        def respond(self, body, content_type, status=200):
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, data, status=200):
            self.respond(json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8'),
                         'application/json', status)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path in ('/', '/index.html'):
                view = preview._view()
                # 전체 표시 자료는 한 번 준비하고 화면 이동 시 클라이언트에서 범위를 거릅니다.
                view.render_hospitals(preview.repository.find_all())
                html = view.render_html(javascript_key).replace(
                    '</body>', '<script src="/static/map_controls.js"></script></body>')
                self.respond(html.encode('utf-8'), 'text/html')
            elif parsed.path in files:
                filename, content_type = files[parsed.path]
                self.respond((ROOT / filename).read_bytes(), content_type)
            elif parsed.path == '/api/district':
                name = parse_qs(parsed.query).get('name', [''])[0]
                try:
                    self.send_json(preview.district(name))
                except ValueError as error:
                    self.send_json({'error': str(error)}, 400)
            else:
                self.send_error(404)

        def do_POST(self):
            if urlparse(self.path).path != '/api/nearby':
                self.send_error(404)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192:
                    raise ValueError('입력 내용을 확인하세요.')
                data = json.loads(self.rfile.read(length).decode('utf-8'))
                if not isinstance(data, dict):
                    raise ValueError('입력 내용을 확인하세요.')
                self.send_json(preview.nearby(data))
            except (ValueError, UnicodeDecodeError) as error:
                self.send_json({'error': str(error)}, 400)
            except Exception:
                # 외부 주소 검색 오류의 상세 요청·키를 응답에 노출하지 않습니다.
                self.send_json({'error': '주소 검색에 실패했습니다. 연결과 API 설정을 확인하세요.'}, 502)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    load_dotenv(args.env_file)
    key = os.getenv('KAKAO_JAVASCRIPT_KEY', '').strip()
    if not key:
        raise SystemExit('.env에 KAKAO_JAVASCRIPT_KEY를 설정하세요.')
    service = LocationService()
    repository = HospitalRepository(service)
    repository.load(ROOT / 'data' / 'seoul_animal_hospitals.csv')
    preview = MapPreview(repository, service)
    server = create_server(preview, key, args.port)
    print(f'지도 접속: http://localhost:{server.server_port}')
    print('종료: Ctrl+C')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
