from unittest.mock import MagicMock

from naas.library.auth import Credentials, device_lockout, job_unlocker, tacacs_auth_lockout


class TestLockout:
    """Test sliding-window lockout for both user (TACACS) and device."""

    def test_no_failures_not_locked(self, fake_redis, monkeypatch):
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)
        assert tacacs_auth_lockout(username="testuser") is False

    def test_first_failure_not_locked(self, fake_redis, monkeypatch):
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)
        assert tacacs_auth_lockout(username="testuser", report_failure=True) is False

    def test_nine_failures_not_locked(self, fake_redis, monkeypatch):
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)
        for _ in range(9):
            tacacs_auth_lockout(username="testuser", report_failure=True)
        assert tacacs_auth_lockout(username="testuser") is False

    def test_tenth_failure_triggers_lockout(self, fake_redis, monkeypatch):
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)
        for _ in range(9):
            tacacs_auth_lockout(username="testuser", report_failure=True)
        assert tacacs_auth_lockout(username="testuser", report_failure=True) is True

    def test_lockout_persists(self, fake_redis, monkeypatch):
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)
        for _ in range(10):
            tacacs_auth_lockout(username="testuser", report_failure=True)
        assert tacacs_auth_lockout(username="testuser") is True

    def test_old_failures_expire(self, fake_redis, monkeypatch):
        """Failures outside the 10-minute window are pruned and don't count."""
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)
        from datetime import datetime, timedelta

        old_ts = (datetime.now() - timedelta(minutes=30)).timestamp()
        for i in range(9):
            fake_redis.zadd("naas_failures_testuser", {f"old-{i}": old_ts})
        assert tacacs_auth_lockout(username="testuser") is False

    def test_old_failures_plus_new_not_locked(self, fake_redis, monkeypatch):
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)
        from datetime import datetime, timedelta

        old_ts = (datetime.now() - timedelta(minutes=30)).timestamp()
        for i in range(9):
            fake_redis.zadd("naas_failures_testuser", {f"old-{i}": old_ts})
        assert tacacs_auth_lockout(username="testuser", report_failure=True) is False

    def test_device_lockout_no_failures(self, fake_redis, monkeypatch):
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)
        assert device_lockout(ip="192.0.2.1") is False

    def test_device_lockout_triggers_at_ten(self, fake_redis, monkeypatch):
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)
        for _ in range(9):
            device_lockout(ip="192.0.2.1", report_failure=True)
        assert device_lockout(ip="192.0.2.1", report_failure=True) is True

    def test_device_lockout_independent_of_user_lockout(self, fake_redis, monkeypatch):
        """Device and user lockouts use separate keys."""
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)
        for _ in range(10):
            tacacs_auth_lockout(username="testuser", report_failure=True)
        assert device_lockout(ip="192.0.2.1") is False


class TestJobUnlocker:
    """Test job unlocking functionality."""

    def test_job_unlock_success(self, app, client):
        """Test successful job unlock with matching credentials."""
        job = app.config["q"].fetch_job("test-job-id")
        job.meta["hash"] = "test-hash"

        with app.app_context():
            assert job_unlocker("test-hash", "test-job-id") is True

    def test_job_unlock_wrong_hash(self, app, client):
        """Test job unlock fails with wrong credentials."""
        job = app.config["q"].fetch_job("test-job-id")
        job.meta["hash"] = "correct-hash"

        with app.app_context():
            assert job_unlocker("wrong-hash", "test-job-id") is False

    def test_job_unlock_no_hash(self, app, client):
        """Test job unlock fails when no hash stored."""
        with app.app_context():
            assert job_unlocker("test-hash", "test-job-id") is False

    def test_job_unlock_exception(self, app, client):
        """Test job unlock handles exceptions gracefully."""
        app.config["q"].fetch_job = MagicMock(side_effect=Exception("Redis error"))

        with app.app_context():
            assert job_unlocker("test-hash", "test-job-id") is False


class TestCredentials:
    """Test Credentials class functionality."""

    def test_credentials_init(self):
        """Test Credentials initialization."""
        creds = Credentials(username="admin", password="secret")
        assert creds.username == "admin"
        assert creds.password == "secret"
        assert creds.enable == "secret"

    def test_credentials_with_enable(self):
        """Test Credentials with separate enable password."""
        creds = Credentials(username="admin", password="secret", enable="enable_secret")
        assert creds.enable == "enable_secret"

    def test_credentials_repr(self):
        """Test Credentials __repr__ redacts passwords."""
        creds = Credentials(username="admin", password="secret")
        repr_str = repr(creds)
        assert "admin" in repr_str
        assert "secret" not in repr_str
        assert "<redacted>" in repr_str

    def test_credentials_str(self):
        """Test Credentials __str__ redacts passwords."""
        creds = Credentials(username="admin", password="secret")
        str_repr = str(creds)
        assert "admin" in str_repr
        assert "secret" not in str_repr
        assert "<redacted>" in str_repr

    def test_credentials_salted_hash_with_salt(self, app, client):
        """Test salted_hash with provided salt."""
        creds = Credentials("testuser", "testpass")

        with app.app_context():
            result = creds.salted_hash(salt="test-salt")
            assert isinstance(result, str)
            assert len(result) == 128  # SHA512 hex digest length

    def test_credentials_salted_hash_from_redis(self, app, client):
        """Test salted_hash fetches salt from Redis when not provided."""
        app.config["redis"].set("naas_cred_salt", b"redis-salt")
        creds = Credentials("testuser", "testpass")

        with app.app_context():
            result = creds.salted_hash()
            assert isinstance(result, str)
            assert len(result) == 128
