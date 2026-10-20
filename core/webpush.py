"""Minimal standards-based Web Push transport for Cora.

No third-party push service is required by Cora itself. Browser push endpoints
(APNs on iOS, browser vendor endpoints elsewhere) are contacted outbound only.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _key_path() -> Path:
    return Path(os.getenv("CORA_PUSH_VAPID_PATH", "/state/push-vapid.json")).expanduser()


def _public_bytes(key: ec.EllipticCurvePrivateKey) -> bytes:
    return key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )


def _private_bytes(key: ec.EllipticCurvePrivateKey) -> bytes:
    value = key.private_numbers().private_value
    return value.to_bytes(32, "big")


def _load_private(value: str) -> ec.EllipticCurvePrivateKey:
    number = int.from_bytes(_unb64(value), "big")
    if not 1 <= number < ec.SECP256R1().key_size ** 32:
        # derive_private_key performs the authoritative curve-order validation.
        pass
    return ec.derive_private_key(number, ec.SECP256R1())


def vapid_key() -> ec.EllipticCurvePrivateKey:
    path = _key_path()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return _load_private(data["private_key"])
    key = ec.generate_private_key(ec.SECP256R1())
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "private_key": _b64(_private_bytes(key)),
        "public_key": _b64(_public_bytes(key)),
        "created_at": int(time.time()),
    }, separators=(",", ":"))
    fd, temporary = tempfile.mkstemp(prefix=".push-vapid-", dir=str(path.parent))
    try:
        os.write(fd, payload.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    return key


def public_key() -> str:
    return _b64(_public_bytes(vapid_key()))


def _jwt(endpoint: str, key: ec.EllipticCurvePrivateKey) -> str:
    parts = urlsplit(endpoint)
    if parts.scheme not in {"https"} or not parts.netloc:
        raise ValueError("Endpoint push non HTTPS.")
    header = _b64(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    claims = _b64(json.dumps({
        "aud": f"{parts.scheme}://{parts.netloc}",
        "exp": int(time.time()) + 12 * 60 * 60,
        "sub": os.getenv("CORA_PUSH_VAPID_SUBJECT", "mailto:cora@localhost"),
    }, separators=(",", ":")).encode())
    signing_input = f"{header}.{claims}".encode("ascii")
    der = key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    signature = _b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"{header}.{claims}.{signature}"


def _encrypt(payload: bytes, p256dh: str, auth: str) -> bytes:
    client_public_bytes = _unb64(p256dh)
    auth_secret = _unb64(auth)
    if len(client_public_bytes) != 65 or client_public_bytes[0] != 4:
        raise ValueError("Chiave p256dh non valida.")
    if len(auth_secret) < 16:
        raise ValueError("Segreto auth push non valido.")

    client_public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), client_public_bytes)
    server_private = ec.generate_private_key(ec.SECP256R1())
    server_public = _public_bytes(server_private)
    shared = server_private.exchange(ec.ECDH(), client_public)

    ikm = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=auth_secret,
        info=b"WebPush: info\x00" + client_public_bytes + server_public,
    ).derive(shared)
    salt = secrets.token_bytes(16)
    cek = HKDF(
        algorithm=hashes.SHA256(),
        length=16,
        salt=salt,
        info=b"Content-Encoding: aes128gcm\x00",
    ).derive(ikm)
    nonce = HKDF(
        algorithm=hashes.SHA256(),
        length=12,
        salt=salt,
        info=b"Content-Encoding: nonce\x00",
    ).derive(ikm)

    # One final RFC 8188 record. Calendar payloads are deliberately tiny.
    plaintext = payload + b"\x02"
    encrypted = AESGCM(cek).encrypt(nonce, plaintext, None)
    record_size = 4096
    if len(encrypted) + 86 > record_size:
        raise ValueError("Payload push troppo grande.")
    return salt + record_size.to_bytes(4, "big") + bytes([len(server_public)]) + server_public + encrypted


class PushGone(Exception):
    """Subscription permanently invalid (404/410)."""


def send(endpoint: str, p256dh: str, auth: str, payload: dict, *, ttl: int = 300) -> None:
    key = vapid_key()
    body = _encrypt(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), p256dh, auth)
    request = Request(endpoint, data=body, method="POST", headers={
        "TTL": str(max(0, min(int(ttl), 86400))),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "Authorization": f"vapid t={_jwt(endpoint, key)}, k={_b64(_public_bytes(key))}",
        "Urgency": "normal",
    })
    try:
        with urlopen(request, timeout=8) as response:
            if response.status not in {200, 201, 202, 204}:
                raise RuntimeError(f"Push HTTP {response.status}")
    except HTTPError as error:
        if error.code in {404, 410}:
            raise PushGone("Subscription push scaduta.") from error
        raise RuntimeError(f"Push HTTP {error.code}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError("Servizio push non raggiungibile.") from error
