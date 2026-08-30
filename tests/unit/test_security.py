"""HMAC contract verification tests."""

import hashlib
import hmac

from fx_platform.api.security import verify_signature


def test_hmac_is_explicitly_optional_when_no_secret_is_configured() -> None:
    assert verify_signature(b"payload", None, None)


def test_hmac_accepts_only_matching_sha256_signature() -> None:
    body = b'{"schema_version":"1.0"}'
    secret = "local-test-secret"
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert verify_signature(body, f"sha256={digest}", secret)
    assert not verify_signature(body, None, secret)
    assert not verify_signature(body, digest, secret)
    assert not verify_signature(body + b" ", f"sha256={digest}", secret)
