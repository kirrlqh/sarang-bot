import os
import http.server
import socketserver
from threading import Thread


class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="static", **kwargs)

    def do_GET(self):
        # Всегда отдаем index.html для любых путей (SPA)
        if self.path != '/' and '.' not in self.path:
            self.path = '/'
        return super().do_GET()


def start_web_server():
    PORT = int(os.getenv('PORT', 8000))

    with socketserver.TCPServer(("", PORT), MyHttpRequestHandler) as httpd:
        print(f"🌐 Web server running on port {PORT}")
        print(f"📱 Mini App available at: http://localhost:{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    start_web_server()