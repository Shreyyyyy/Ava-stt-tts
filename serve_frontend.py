"""
Serve the AVA frontend on port 3000.
Run this alongside main.py to access the UI locally.
"""
import http.server
import socketserver
from pathlib import Path
import webbrowser
import threading

PORT = 3000
FRONTEND_DIR = Path(__file__).parent / "frontend"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def log_message(self, format, *args):
        pass  # suppress noise


def open_browser():
    import time
    time.sleep(0.8)
    webbrowser.open(f"http://localhost:{PORT}")


if __name__ == "__main__":
    print(f"🌐 Frontend running at http://localhost:{PORT}")
    threading.Thread(target=open_browser, daemon=True).start()
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
