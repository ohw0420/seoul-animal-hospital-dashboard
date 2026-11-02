import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from dotenv import load_dotenv

from src.hospital_map_view import HospitalMapView


def main():
    project_root = Path(__file__).resolve().parent
    load_dotenv(project_root / ".env")

    javascript_key = os.getenv("KAKAO_JAVASCRIPT_KEY", "").strip()
    if not javascript_key:
        raise SystemExit(
            ".env에 KAKAO_JAVASCRIPT_KEY를 입력하세요."
        )

    view = HospitalMapView()

    view.render_hospitals([
        {
            "name": "동물병원 1",
            "status": "정상영업",
            "phone": "02-111-1111",
            "address": "서울시 노원구 시연용 주소",
            "latitude": 37.6215,
            "longitude": 127.0575,
        },
        {
            "name": "동물병원 2",
            "status": "정상영업",
            "phone": None,
            "address": "서울시 노원구 시연용 주소",
            "latitude": 37.6170,
            "longitude": 127.0560,
        },
        {
            "name": "동물병원 3",
            "status": "휴업",
            "phone": "02-333-3333",
            "address": "서울시 노원구 시연용 주소",
            "latitude": 37.6180,
            "longitude": 127.0640,
        },
    ])

    view.show_user_location(37.6194, 127.0598)
    view.show_search_radius(1000)

    class MapHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/", "/index.html"):
                self.send_error(404)
                return

            content = view.render_html(javascript_key).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    server = HTTPServer(("127.0.0.1", 8000), MapHandler)
    print("접속 주소: http://localhost:8000")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n지도 시연을 종료합니다.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
