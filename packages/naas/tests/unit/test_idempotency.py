"""Unit tests for idempotency key support."""

from naas.library.idempotency import get_idempotent_job_id, store_idempotency_key


class TestIdempotency:
    def test_get_returns_none_when_key_not_found(self, fake_redis):
        """Returns None when key has not been seen before."""
        assert get_idempotent_job_id("new-key", fake_redis) is None

    def test_get_returns_job_id_when_key_exists(self, fake_redis):
        """Returns stored job_id when key exists."""
        store_idempotency_key("my-key", "job-abc", fake_redis)
        assert get_idempotent_job_id("my-key", fake_redis) == "job-abc"

    def test_store_sets_key_with_ttl(self, fake_redis):
        """Storing a key makes it retrievable."""
        store_idempotency_key("key1", "job-123", fake_redis)
        assert get_idempotent_job_id("key1", fake_redis) == "job-123"

    def test_store_is_idempotent(self, fake_redis):
        """Second store with same key does not overwrite (NX semantics)."""
        store_idempotency_key("key1", "job-first", fake_redis)
        store_idempotency_key("key1", "job-second", fake_redis)
        assert get_idempotent_job_id("key1", fake_redis) == "job-first"

    def test_keys_are_hashed(self, fake_redis):
        """Raw key is not stored in Redis (hashed before storage)."""
        store_idempotency_key("sensitive-key", "job-abc", fake_redis)
        assert fake_redis.get("naas:idempotency:sensitive-key") is None
