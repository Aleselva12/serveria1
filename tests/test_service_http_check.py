"""Immich/Nextcloud reachability check: tell 'answered with an error' from 'unreachable'."""
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from core.additional_verifications import service_http


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/ui" and "json" in self.headers.get("Accept", ""):
            self.send_response(406)  # what the Immich web root does for Accept: application/json
        elif self.path == "/moved":
            self.send_response(302)
            self.send_header("Location", "https://example.invalid/login")
        elif self.path == "/broken":
            self.send_response(503)
        else:
            self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


class ServiceHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def check(self, url):
        with patch.dict(os.environ, {"CORA_SERVICE_IMMICH_URL": url}):
            return service_http("immich")

    def test_a_web_root_is_not_asked_for_json_only(self):
        self.assertEqual(self.check(self.base + "/ui")[0], "pass")

    def test_redirects_and_errors_say_the_service_answered(self):
        status, detail = self.check(self.base + "/moved")
        self.assertEqual(status, "fail")
        self.assertIn("reindirizzamento (302)", detail)
        status, detail = self.check(self.base + "/broken")
        self.assertEqual(status, "fail")
        self.assertIn("raggiungibile ma risponde 503", detail)

    def test_a_closed_port_is_unreachable(self):
        with HTTPServer(("127.0.0.1", 0), Handler) as closed:
            port = closed.server_port
        status, detail = self.check(f"http://127.0.0.1:{port}/")
        self.assertEqual((status, detail), ("fail", "Endpoint HTTP del servizio non raggiungibile"))

    def test_missing_or_credentialed_urls_are_not_probed(self):
        self.assertEqual(self.check("")[0], "unknown")
        self.assertEqual(self.check("http://user:secret@127.0.0.1/")[0], "unknown")
        self.assertEqual(self.check("file:///etc/passwd")[0], "unknown")


if __name__ == "__main__":
    unittest.main()
