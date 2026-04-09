"""Unit tests for job deduplication."""

from naas.library.dedup import clear_dedup_key, get_duplicate_job_id, register_dedup_key


class TestDedup:
    def test_get_returns_none_when_no_duplicate(self, fake_redis):
        """Returns None when no in-flight job exists."""
        assert get_duplicate_job_id("host", "cisco_ios", ["show version"], "user", fake_redis) is None

    def test_get_returns_job_id_when_duplicate_exists(self, fake_redis):
        """Returns existing job_id when duplicate is in-flight."""
        register_dedup_key("host", "cisco_ios", ["show version"], "user", "job-abc", fake_redis)
        assert get_duplicate_job_id("host", "cisco_ios", ["show version"], "user", fake_redis) == "job-abc"

    def test_different_users_not_deduplicated(self, fake_redis):
        """Same host+commands for different users are not deduplicated."""
        register_dedup_key("host", "cisco_ios", ["show version"], "user1", "job-1", fake_redis)
        assert get_duplicate_job_id("host", "cisco_ios", ["show version"], "user2", fake_redis) is None

    def test_commands_order_independent(self, fake_redis):
        """Command order doesn't affect dedup key."""
        register_dedup_key("host", "cisco_ios", ["cmd-b", "cmd-a"], "user", "job-abc", fake_redis)
        assert get_duplicate_job_id("host", "cisco_ios", ["cmd-a", "cmd-b"], "user", fake_redis) == "job-abc"

    def test_register_returns_redis_key(self, fake_redis):
        """register_dedup_key returns the Redis key for storage in job.meta."""
        key = register_dedup_key("host", "cisco_ios", ["show version"], "user", "job-abc", fake_redis)
        assert key.startswith("naas:dedup:")

    def test_register_is_nx(self, fake_redis):
        """Second register with same params does not overwrite (NX semantics)."""
        register_dedup_key("host", "cisco_ios", ["show version"], "user", "job-first", fake_redis)
        register_dedup_key("host", "cisco_ios", ["show version"], "user", "job-second", fake_redis)
        assert get_duplicate_job_id("host", "cisco_ios", ["show version"], "user", fake_redis) == "job-first"

    def test_clear_removes_key(self, fake_redis):
        """clear_dedup_key removes the key so next request enqueues fresh."""
        key = register_dedup_key("host", "cisco_ios", ["show version"], "user", "job-abc", fake_redis)
        clear_dedup_key(key, fake_redis)
        assert get_duplicate_job_id("host", "cisco_ios", ["show version"], "user", fake_redis) is None

    def test_clear_empty_key_is_noop(self, fake_redis):
        """clear_dedup_key with empty string is a no-op."""
        clear_dedup_key("", fake_redis)  # Should not raise

    def test_disabled_returns_none(self, fake_redis, monkeypatch):
        """When JOB_DEDUP_ENABLED=False, get always returns None."""
        monkeypatch.setattr("naas.library.dedup.JOB_DEDUP_ENABLED", False)
        register_dedup_key("host", "cisco_ios", ["show version"], "user", "job-abc", fake_redis)
        assert get_duplicate_job_id("host", "cisco_ios", ["show version"], "user", fake_redis) is None

    def test_disabled_register_returns_empty(self, fake_redis, monkeypatch):
        """When JOB_DEDUP_ENABLED=False, register returns empty string."""
        monkeypatch.setattr("naas.library.dedup.JOB_DEDUP_ENABLED", False)
        key = register_dedup_key("host", "cisco_ios", ["show version"], "user", "job-abc", fake_redis)
        assert key == ""
