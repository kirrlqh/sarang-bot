import os
import http.server
import socketserver

print("🔄 WEB SERVER: Starting...")
print(f"📁 WEB SERVER: Current directory: {os.getcwd()}")

try:
    files = os.listdir('static')
    print(f"📁 WEB SERVER: Static files: {files}")
except Exception as e:
    print(f"❌ WEB SERVER: Error listing static: {e}")


class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="static", **kwargs)

    def do_GET(self):
        if self.path != '/' and '.' not in self.path:
            self.path = '/'
        return super().do_GET()


def start_web_server():
    PORT = int(os.getenv('PORT', 8000))
    print(f"🌐 WEB SERVER: Starting on port {PORT}")

    with socketserver.TCPServer(("", PORT), MyHttpRequestHandler) as httpd:
        print(f"✅ WEB SERVER: Running on port {PORT}")
        print(f"📱 WEB SERVER: Mini App available!")
        httpd.serve_forever()


if __name__ == "__main__":
    start_web_server()