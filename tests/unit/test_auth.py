from datetime import datetime, timedelta
from pickle import dumps
from unittest.mock import MagicMock

from naas.library.auth import Credentials, job_unlocker, report_tacacs_failure, tacacs_auth_lockout


class TestTacacsAuthLockout:
    """Test TACACS authentication lockout functionality."""

    def test_no_failures_no_report(self, fake_redis, monkeypatch):
        """Test checking failures when none exist and not reporting."""
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)
        assert tacacs_auth_lockout(username="testuser") is False

    def test_first_failure_report(self, fake_redis, monkeypatch):
        """Test reporting the first failure."""
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)
        assert tacacs_auth_lockout(username="testuser", report_failure=True) is False

        failures = fake_redis.hgetall("naas_failures_testuser")
        assert int(failures[b"failure_count"]) == 1

    def test_nine_failures_no_lockout(self, fake_redis, monkeypatch):
        """Test that 9 failures don't trigger lockout."""
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)

        for _ in range(9):
            tacacs_auth_lockout(username="testuser", report_failure=True)

        assert tacacs_auth_lockout(username="testuser") is False

    def test_tenth_failure_triggers_lockout(self, fake_redis, monkeypatch):
        """Test that the 10th failure triggers lockout."""
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)

        for _ in range(9):
            tacacs_auth_lockout(username="testuser", report_failure=True)

        assert tacacs_auth_lockout(username="testuser", report_failure=True) is True

    def test_lockout_persists(self, fake_redis, monkeypatch):
        """Test that lockout persists after 10 failures."""
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)

        for _ in range(10):
            tacacs_auth_lockout(username="testuser", report_failure=True)

        assert tacacs_auth_lockout(username="testuser") is True
        assert tacacs_auth_lockout(username="testuser", report_failure=True) is True

    def test_old_failures_expire(self, fake_redis, monkeypatch):
        """Test that failures older than 10 minutes are removed."""
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)

        # Create 9 old failures
        old_timestamps = [datetime.now() - timedelta(minutes=30) for _ in range(9)]
        fail_dict = {"failure_count": 9, "failure_timestamps": dumps(old_timestamps)}
        fake_redis.hset("naas_failures_testuser", mapping=fail_dict)

        assert tacacs_auth_lockout(username="testuser") is False

    def test_old_failures_expire_new_failure_allowed(self, fake_redis, monkeypatch):
        """Test that new failure after old ones expire doesn't trigger lockout."""
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)

        old_timestamps = [datetime.now() - timedelta(minutes=30) for _ in range(9)]
        fail_dict = {"failure_count": 9, "failure_timestamps": dumps(old_timestamps)}
        fake_redis.hset("naas_failures_testuser", mapping=fail_dict)

        assert tacacs_auth_lockout(username="testuser", report_failure=True) is False

    def test_mixed_old_and_new_failures(self, fake_redis, monkeypatch):
        """Test lockout with mix of old and new failures."""
        monkeypatch.setattr("naas.library.auth.Redis", lambda **kwargs: fake_redis)

        # 5 old failures + 9 new = should trigger lockout on 10th
        old_timestamps = [datetime.now() - timedelta(minutes=30) for _ in range(5)]
        fail_dict = {"failure_count": 5, "failure_timestamps": dumps(old_timestamps)}
        fake_redis.hset("naas_failures_testuser", mapping=fail_dict)

        for _ in range(9):
            tacacs_auth_lockout(username="testuser", report_failure=True)

        assert tacacs_auth_lockout(username="testuser", report_failure=True) is True


class TestReportTacacsFailure:
    """Test TACACS failure reporting."""

    def test_report_first_failure(self, fake_redis):
        """Test reporting the first failure."""
        report_tacacs_failure(username="testuser", existing_fail_count=0, existing_fail_times=[], redis=fake_redis)

        failures = fake_redis.hgetall("naas_failures_testuser")
        assert int(failures[b"failure_count"]) == 1

    def test_report_increments_count(self, fake_redis):
        """Test that reporting increments the failure count."""
        existing_times = [datetime.now()]

        report_tacacs_failure(
            username="testuser", existing_fail_count=1, existing_fail_times=existing_times, redis=fake_redis
        )

        failures = fake_redis.hgetall("naas_failures_testuser")
        assert int(failures[b"failure_count"]) == 2


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
