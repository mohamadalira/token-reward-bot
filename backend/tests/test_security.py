import hashlib
import hmac

from app.core.security import verify_plisio_signature


def test_plisio_signature_invalid():
    data = {"status": "completed", "txn_id": "123"}
    assert verify_plisio_signature(dict(data), "secret") is False


def test_plisio_signature_valid():
    data = {"amount": "10", "status": "completed", "txn_id": "abc123"}
    sorted_items = sorted(data.items())
    sign_string = "|".join(str(v) for _, v in sorted_items)
    verify_hash = hmac.new(
        b"testsecret",
        sign_string.encode(),
        hashlib.sha1,
    ).hexdigest()
    data_with_hash = {**data, "verify_hash": verify_hash}
    assert verify_plisio_signature(data_with_hash, "testsecret") is True
