from __future__ import annotations

import hmac
import ipaddress
import os
from collections.abc import Callable

from fastapi import HTTPException, Request


LEGACY_TOKEN_ENV = {
    "files": "CORA_FILES_TOKEN",
    "calendar": "CORA_CALENDAR_TOKEN",
    "automation": "CORA_FILES_TOKEN",
    "permissions": "CORA_FILES_TOKEN",
    "runtime": "CORA_FILES_TOKEN",
}


def is_loopback(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_loopback


def configured_owner_token(scope: str = "") -> str:
    shared = os.getenv("CORA_OWNER_TOKEN", "").strip()
    if shared:
        return shared
    legacy = LEGACY_TOKEN_ENV.get(scope)
    return os.getenv(legacy, "").strip() if legacy else ""


def require_owner(request: Request, scope: str = "") -> None:
    """
    Owner gate shared by protected APIs.

    CORA_OWNER_TOKEN is authoritative when configured. During migration, File
    and Calendar keep their legacy token fallback. Without a token only direct
    loopback is accepted.
    """
    token = configured_owner_token(scope)
    if token:
        supplied = request.headers.get("authorization", "")
        expected = "Bearer " + token
        if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
            raise HTTPException(401, "Accesso proprietario non autorizzato.")
        return

    host = request.client.host if request.client else ""
    if not is_loopback(host):
        raise HTTPException(403, "Configura CORA_OWNER_TOKEN per l'accesso remoto.")


def owner_dependency(scope: str = "") -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        require_owner(request, scope)
    return dependency
