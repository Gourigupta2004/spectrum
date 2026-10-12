"""
Reversible encryption for the few secrets an admin must be able to read back
(institution portal passwords), using only the standard library.

HMAC-SHA256 serves as the pseudo-random function in counter mode for the
keystream, with encrypt-then-MAC: a random 16-byte nonce, the XORed text,
and an HMAC-SHA256 tag over both. Both keys are derived from SECRET_KEY, so
the text in the database is unreadable without it — and if SECRET_KEY ever
changes, old values can no longer be shown (sign-in, which checks a separate
hash, keeps working).
"""

import base64
import hashlib
import hmac
import secrets

from django.utils.crypto import salted_hmac

PREFIX = "v1$"


def _keys() -> tuple[bytes, bytes]:
    return (salted_hmac("core.crypto.encrypt", "key", algorithm="sha256").digest(),
            salted_hmac("core.crypto.mac", "key", algorithm="sha256").digest())


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    blocks = (hmac.new(key, nonce + i.to_bytes(4, "big"), hashlib.sha256).digest()
              for i in range((length + 31) // 32))
    return b"".join(blocks)[:length]


def encrypt(text: str) -> str:
    if not text:
        return ""
    enc_key, mac_key = _keys()
    nonce = secrets.token_bytes(16)
    data = text.encode()
    body = bytes(a ^ b for a, b in zip(data, _keystream(enc_key, nonce, len(data))))
    tag = hmac.new(mac_key, nonce + body, hashlib.sha256).digest()
    return PREFIX + base64.urlsafe_b64encode(nonce + body + tag).decode()


def decrypt(token: str) -> str:
    """The original text, or "" if the token is empty, tampered with, or was
    made with a different SECRET_KEY."""
    if not token or not token.startswith(PREFIX):
        return ""
    try:
        raw = base64.urlsafe_b64decode(token[len(PREFIX):].encode())
    except ValueError:
        return ""
    if len(raw) < 48:
        return ""
    nonce, body, tag = raw[:16], raw[16:-32], raw[-32:]
    enc_key, mac_key = _keys()
    if not hmac.compare_digest(tag, hmac.new(mac_key, nonce + body, hashlib.sha256).digest()):
        return ""
    data = bytes(a ^ b for a, b in zip(body, _keystream(enc_key, nonce, len(body))))
    try:
        return data.decode()
    except UnicodeDecodeError:
        return ""
