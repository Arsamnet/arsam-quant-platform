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
    expected_digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided_digest, expected_digest)
