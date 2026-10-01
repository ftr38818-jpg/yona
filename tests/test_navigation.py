"""Offline end-to-end tests: a local HTTP server replaces the real spa site."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import os
from threading import Thread
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from monitor import CheckError, inspect_calendar
from test_monitor import fixture


@unittest.skipUnless(os.getenv("RUN_HTTP_TESTS") == "1", "Optional HTTP tests; require a browser allowed to reach localhost.")
class NavigationTests(unittest.TestCase):
    def run_site(self, offers, api_error=False):
        body = fixture(offers=offers)
        if api_error:
            body = body.replace('</body>', '<script>fetch("/availability");</script></body>')

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == '/availability':
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b'not available')
                    return
                content = '<html><body><a href="/calendar">Reserver Yonaguni</a></body></html>' if self.path == '/' else body
                data = content.encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            return inspect_calendar({'url':f'http://127.0.0.1:{server.server_port}/', 'target_date':'2026-10-08', 'people':2})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_click_wait_and_available(self):
        result = self.run_site({'2026-10-08':['Night']})
        self.assertEqual(result['offers'], ['Night'])

    def test_click_wait_and_unavailable(self):
        result = self.run_site({'2026-10-02':['Day']})
        self.assertEqual(result['status'], 'unavailable')

    def test_failed_data_request_is_not_unavailable(self):
        with self.assertRaisesRegex(CheckError, 'Une requete de donnees'):
            self.run_site({'2026-10-02':['Day']}, api_error=True)


if __name__ == '__main__':
    unittest.main()
