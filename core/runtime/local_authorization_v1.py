# -*- coding: utf-8 -*-
"""Trusted-local request authentication for privileged ArchitectOS actions.

This module authenticates the UI gateway process to the Core API.  It is not
an Internet/multi-user identity system and it grants no authority by itself;
the resulting context must still be checked by the owner of each privileged
operation.  Signatures are short-lived and nonce-bound so a captured request
cannot be replayed within the accepted clock window.
"""

import hashlib
import hmac
import ipaddress
import json
import threading
import time
from urllib.parse import urlsplit


HEADER_ACTOR = "X-ArchitectOS-Actor"
HEADER_SESSION = "X-ArchitectOS-Local-Session"
HEADER_TIMESTAMP = "X-ArchitectOS-Timestamp"
HEADER_NONCE = "X-ArchitectOS-Nonce"
HEADER_SIGNATURE = "X-ArchitectOS-Signature"
MAX_CLOCK_SKEW_SECONDS = 60


def _loopback(value):
    value = str(value or "").strip().split("%", 1)[0]
    if value.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _canonical_payload(payload):
    if not isinstance(payload, dict):
        payload = {}
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        default=str,
    )


def _signed_message(actor_id, session_id, timestamp, nonce, path, payload):
    return "\n".join((
        str(actor_id), str(session_id), str(timestamp), str(nonce), str(path),
        hashlib.sha256(_canonical_payload(payload).encode("utf-8")).hexdigest(),
    )).encode("utf-8")


class LocalRequestNonceLedger:
    """Bounded in-process ledger for accepted proxy nonces."""

    def __init__(self, max_entries=4096):
        self.max_entries = max(64, int(max_entries))
        self._seen = {}
        self._lock = threading.Lock()

    def consume(self, nonce, now, ttl=MAX_CLOCK_SKEW_SECONDS * 2):
        with self._lock:
            cutoff = float(now) - float(ttl)
            self._seen = {key: value for key, value in self._seen.items() if value >= cutoff}
            if nonce in self._seen:
                return False
            if len(self._seen) >= self.max_entries:
                oldest = min(self._seen, key=self._seen.get)
                self._seen.pop(oldest, None)
            self._seen[nonce] = float(now)
            return True


DEFAULT_NONCE_LEDGER = LocalRequestNonceLedger()


def sign_proxy_request(secret, actor_id, session_id, payload, path="/chat", now=None, nonce=None):
    import secrets

    if not isinstance(secret, str) or len(secret) < 32:
        raise ValueError("local_proxy_secret_too_short")
    now = int(time.time() if now is None else now)
    nonce = nonce or ("nonce_" + secrets.token_hex(16))
    signature = hmac.new(
        secret.encode("utf-8"),
        _signed_message(actor_id, session_id, now, nonce, path, payload),
        hashlib.sha256,
    ).hexdigest()
    return {
        HEADER_ACTOR: str(actor_id),
        HEADER_SESSION: str(session_id),
        HEADER_TIMESTAMP: str(now),
        HEADER_NONCE: str(nonce),
        HEADER_SIGNATURE: signature,
    }


def verify_proxy_request(secret, headers, payload, path="/chat", remote_addr=None,
                         now=None, nonce_ledger=None):
    result = {"trusted": False, "source": "trusted_local_ui_proxy"}
    if not _loopback(remote_addr):
        result["reason"] = "proxy_not_loopback"
        return result
    if not isinstance(secret, str) or len(secret) < 32:
        result["reason"] = "proxy_secret_unavailable"
        return result
    actor = str(headers.get(HEADER_ACTOR, ""))
    session = str(headers.get(HEADER_SESSION, ""))
    nonce = str(headers.get(HEADER_NONCE, ""))
    signature = str(headers.get(HEADER_SIGNATURE, ""))
    try:
        timestamp = int(headers.get(HEADER_TIMESTAMP, ""))
    except (TypeError, ValueError):
        result["reason"] = "proxy_timestamp_invalid"
        return result
    current = int(time.time() if now is None else now)
    if abs(current - timestamp) > MAX_CLOCK_SKEW_SECONDS:
        result["reason"] = "proxy_signature_expired"
        return result
    if not actor.startswith("lsa_") or not session.startswith("lss_") or not nonce.startswith("nonce_"):
        result["reason"] = "proxy_identity_invalid"
        return result
    expected = hmac.new(
        secret.encode("utf-8"),
        _signed_message(actor, session, timestamp, nonce, path, payload),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        result["reason"] = "proxy_signature_invalid"
        return result
    ledger = nonce_ledger or DEFAULT_NONCE_LEDGER
    if not ledger.consume(nonce, current):
        result["reason"] = "proxy_nonce_replayed"
        return result
    result.update({"trusted": True, "reason": None, "actor_id": actor, "session_id": session})
    return result


def ui_request_is_trusted_origin(origin, host, remote_addr, ui_url):
    """Require a loopback browser request whose Origin and Host match the UI."""
    if not _loopback(remote_addr):
        return False
    try:
        expected = urlsplit(str(ui_url))
        supplied = urlsplit(str(origin))
    except Exception:
        return False
    expected_host = expected.netloc.lower()
    return (
        supplied.scheme in ("http", "https")
        and supplied.netloc.lower() == expected_host
        and str(host or "").lower() == expected_host
    )

