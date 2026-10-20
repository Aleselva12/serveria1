import base64
import os
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from core import webpush


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class _Response:
    status = 201
    def __enter__(self): return self
    def __exit__(self, *args): return False


class WebPushTests(unittest.TestCase):
    def test_vapid_key_persists_and_send_builds_encrypted_request(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"CORA_PUSH_VAPID_PATH": os.path.join(directory, "vapid.json")},
        ):
            first = webpush.public_key()
            second = webpush.public_key()
            self.assertEqual(first, second)
            self.assertTrue(os.path.isfile(os.path.join(directory, "vapid.json")))

            client = ec.generate_private_key(ec.SECP256R1())
            p256dh = b64(client.public_key().public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            ))
            auth = b64(os.urandom(16))
            captured = {}

            def fake_urlopen(request, timeout=0):
                captured["request"] = request
                captured["timeout"] = timeout
                return _Response()

            with patch.object(webpush, "urlopen", side_effect=fake_urlopen):
                webpush.send(
                    "https://push.example.test/subscription/123",
                    p256dh,
                    auth,
                    {"title": "Cora", "body": "Test", "url": "/#calendar"},
                )

            request = captured["request"]
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.headers["Content-encoding"], "aes128gcm")
            self.assertTrue(request.headers["Authorization"].startswith("vapid t="))
            self.assertGreater(len(request.data), 100)
            self.assertEqual(captured["timeout"], 8)


if __name__ == "__main__":
    unittest.main()
