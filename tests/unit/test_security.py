"""HMAC contract verification tests."""

import hashlib
import hmac

from fx_platform.api.security import verify_local_token, verify_signature


def test_hmac_is_explicitly_optional_when_no_secret_is_configured() -> None:
    assert verify_signature(b"payload", None, None)
    assert verify_signature(b"payload", None, "")


def test_hmac_accepts_only_matching_sha256_signature() -> None:
    body = b'{"schema_version":"1.0"}'
    secret = "local-test-secret"
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert verify_signature(body, f"sha256={digest}", secret)
    assert not verify_signature(body, None, secret)
    assert not verify_signature(body, digest, secret)
    assert not verify_signature(body + b" ", f"sha256={digest}", secret)


def test_hmac_rejects_malformed_and_incorrect_digests() -> None:
    body = b"exact raw bytes"
    secret = "local-test-secret"

    assert not verify_signature(body, "sha256=not-hex", secret)
    assert not verify_signature(body, f"sha256={'z' * 64}", secret)
    assert not verify_signature(body, f"sha256={'0' * 62}", secret)
    assert not verify_signature(body, f"sha256={'0' * 64}", secret)
    assert not verify_signature(body, f"sha256={'0' * 66}", secret)


def test_demo_execution_token_fails_closed_and_requires_exact_match() -> None:
    secret = "synthetic-demo-token-with-at-least-32-characters"

    assert verify_local_token(secret, secret)
    assert not verify_local_token(None, secret)
    assert not verify_local_token(secret, None)
    assert not verify_local_token("different-synthetic-demo-token-value", secret)
