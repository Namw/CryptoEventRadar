from crypto_market_intel.sources.base import compute_content_hash


def test_content_hash_stable_for_same_payload():
    payload_a = {"b": 2, "a": 1}
    payload_b = {"a": 1, "b": 2}

    assert compute_content_hash(payload_a) == compute_content_hash(payload_b)
