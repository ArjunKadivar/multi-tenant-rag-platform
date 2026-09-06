from app.security import generate_api_key, hash_api_key


def test_generated_keys_are_unique_and_prefixed():
    keys = {generate_api_key() for _ in range(50)}
    assert len(keys) == 50
    assert all(k.startswith("rag_") for k in keys)


def test_hash_is_deterministic_and_one_way():
    key = generate_api_key()
    hash1 = hash_api_key(key)
    hash2 = hash_api_key(key)
    assert hash1 == hash2
    assert hash1 != key
    assert len(hash1) == 64  # sha256 hex digest length
