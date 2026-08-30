"""Optional raw-body HMAC verification for localhost defense in depth."""

import hashlib
import hmac


def verify_signature(body: bytes, provided_signature: str | None, secret: str | None) -> bool:
    """Verify `sha256=<hex>` using constant-time comparison; no secret means explicitly disabled."""
    if secret is None or not secret:
        return True
    if provided_signature is None or not provided_signature.startswith("sha256="):
        return False
    provided_digest = provided_signature.removeprefix("sha256=")
    if len(provided_digest) != hashlib.sha256().digest_size * 2:
        return False
    try:
        provided_digest_bytes = bytes.fromhex(provided_digest)
    except ValueError:
        return False
    expected_digest = hmac.digest(secret.encode(), body, hashlib.sha256)
    return hmac.compare_digest(provided_digest_bytes, expected_digest)
