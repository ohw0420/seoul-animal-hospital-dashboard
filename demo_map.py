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
            "name": "샘플 행복동물병원",
            "status": "정상영업",
            "phone": "샘플 번호",
            "address": "서울 중구 시연용 주소",
            "latitude": 37.5665,
            "longitude": 126.9780,
        },
        {
            "name": "샘플 사랑동물병원",
            "status": "휴업",
            "phone": None,
            "address": "서울 중구 시연용 주소",
            "latitude": 37.5635,
            "longitude": 126.9840,
        },
        {
            "name": "샘플 폐업병원",
            "status": "폐업",
            "phone": None,
            "address": "표시 제외 확인용",
            "latitude": 37.5680,
            "longitude": 126.9820,
        },
    ])

    view.show_user_location(37.5650, 126.9800)
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
    print("종료: Ctrl+C")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n지도 시연을 종료합니다.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
