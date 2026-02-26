"""Unit tests for netmiko_lib functions."""

from unittest.mock import MagicMock, patch

import netmiko
import pytest
from fakeredis import FakeStrictRedis
from paramiko import ssh_exception  # type: ignore[import-untyped]

import naas.library.netmiko_lib

# Import module first, then replace Redis client
from naas.config import CIRCUIT_BREAKER_THRESHOLD, CIRCUIT_BREAKER_TIMEOUT
from naas.library.auth import Credentials

naas.library.netmiko_lib._redis_client = FakeStrictRedis(decode_responses=True)

from naas.library.netmiko_lib import netmiko_send_command, netmiko_send_config  # noqa: E402


class TestNetmikoSendCommand:
    """Tests for netmiko_send_command function."""

    def test_successful_command(self):
        """Test successful command execution."""
        creds = Credentials(username="testuser", password="testpass")
        commands = ["show version", "show interfaces"]

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_conn = MagicMock()
            mock_conn.send_command.side_effect = ["version output", "interfaces output"]
            mock_handler.return_value = mock_conn

            result, error = netmiko_send_command("192.168.1.1", creds, "cisco_ios", commands)

            assert error is None
            assert result == {"show version": "version output", "show interfaces": "interfaces output"}
            mock_conn.disconnect.assert_called_once()

    def test_timeout_error(self):
        """Test timeout exception is re-raised for RQ retry."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_handler.side_effect = netmiko.NetMikoTimeoutException("Connection timeout")

            with pytest.raises(netmiko.NetMikoTimeoutException):
                netmiko_send_command("192.168.1.1", creds, "cisco_ios", ["show version"])

    def test_auth_failure(self):
        """Test authentication failure handling."""
        creds = Credentials(username="testuser", password="wrongpass")

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            with patch("naas.library.netmiko_lib.tacacs_auth_lockout") as mock_lockout:
                mock_handler.side_effect = netmiko.NetMikoAuthenticationException("Auth failed")

                result, error = netmiko_send_command("192.168.1.1", creds, "cisco_ios", ["show version"])

                assert result is None
                assert "Auth failed" in error
                mock_lockout.assert_called_once_with(username="testuser", report_failure=True)

    def test_ssh_exception(self):
        """Test SSH exception is re-raised for RQ retry."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_handler.side_effect = ssh_exception.SSHException("SSH error")

            with pytest.raises(ssh_exception.SSHException):
                netmiko_send_command("192.168.1.1", creds, "cisco_ios", ["show version"])


class TestNetmikoSendConfig:
    """Tests for netmiko_send_config function."""

    def test_successful_config(self):
        """Test successful config execution."""
        creds = Credentials(username="testuser", password="testpass")
        commands = ["interface GigabitEthernet0/1", "description Test"]

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_conn = MagicMock()
            mock_conn.send_config_set.return_value = "config output"
            mock_handler.return_value = mock_conn

            result, error = netmiko_send_config("192.168.1.1", creds, "cisco_ios", commands)

            assert error is None
            assert result == {"config_set_output": "config output"}
            mock_conn.disconnect.assert_called_once()

    def test_config_with_save(self):
        """Test config with save_config option."""
        creds = Credentials(username="testuser", password="testpass")
        commands = ["interface GigabitEthernet0/1"]

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_conn = MagicMock()
            mock_conn.send_config_set.return_value = "config output"
            mock_handler.return_value = mock_conn

            result, error = netmiko_send_config("192.168.1.1", creds, "cisco_ios", commands, save_config=True)

            assert error is None
            mock_conn.save_config.assert_called_once()

    def test_config_save_not_implemented(self):
        """Test config when save_config is not implemented."""
        creds = Credentials(username="testuser", password="testpass")
        commands = ["interface GigabitEthernet0/1"]

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_conn = MagicMock()
            mock_conn.send_config_set.return_value = "config output"
            mock_conn.save_config.side_effect = NotImplementedError()
            mock_handler.return_value = mock_conn

            result, error = netmiko_send_config("192.168.1.1", creds, "cisco_ios", commands, save_config=True)

            assert error is None
            assert result is not None

    def test_config_with_commit(self):
        """Test config with commit option."""
        creds = Credentials(username="testuser", password="testpass")
        commands = ["interface GigabitEthernet0/1"]

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_conn = MagicMock()
            mock_conn.send_config_set.return_value = "config output"
            mock_handler.return_value = mock_conn

            result, error = netmiko_send_config("192.168.1.1", creds, "cisco_ios", commands, commit=True)

            assert error is None
            mock_conn.commit.assert_called_once()

    def test_config_commit_not_supported(self):
        """Test config when commit is not supported."""
        creds = Credentials(username="testuser", password="testpass")
        commands = ["interface GigabitEthernet0/1"]

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_conn = MagicMock()
            mock_conn.send_config_set.return_value = "config output"
            del mock_conn.commit  # Remove commit attribute
            mock_handler.return_value = mock_conn

            result, error = netmiko_send_config("192.168.1.1", creds, "cisco_ios", commands, commit=True)

            assert error is None
            assert result is not None

    def test_config_timeout_error(self):
        """Test config timeout exception is re-raised for RQ retry."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_handler.side_effect = TimeoutError("Connection timeout")

            with pytest.raises(TimeoutError):
                netmiko_send_config("192.168.1.1", creds, "cisco_ios", ["interface Gi0/1"])

    def test_config_auth_failure(self):
        """Test config authentication failure handling."""
        creds = Credentials(username="testuser", password="wrongpass")

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            with patch("naas.library.netmiko_lib.tacacs_auth_lockout") as mock_lockout:
                mock_handler.side_effect = netmiko.NetMikoAuthenticationException("Auth failed")

                result, error = netmiko_send_config("192.168.1.1", creds, "cisco_ios", ["interface Gi0/1"])

                assert result is None
                assert "Auth failed" in error
                mock_lockout.assert_called_once_with(username="testuser", report_failure=True)

    def test_config_value_error(self):
        """Test config ValueError is re-raised for RQ retry."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_handler.side_effect = ValueError("Invalid value")

            with pytest.raises(ValueError):
                netmiko_send_config("192.168.1.1", creds, "cisco_ios", ["interface Gi0/1"])


class TestCircuitBreaker:
    """Tests for circuit breaker functionality."""

    @pytest.fixture(autouse=True)
    def reset_circuit_breakers(self, monkeypatch):
        """Provide isolated circuit breakers per test via fresh fakeredis."""
        import pybreaker
        from fakeredis import FakeStrictRedis

        import naas.library.netmiko_lib as netmiko_lib
        from naas.config import CIRCUIT_BREAKER_THRESHOLD

        fresh_redis = FakeStrictRedis(decode_responses=True)
        fresh_breakers: dict = {}

        def fresh_get_circuit_breaker(device_id: str) -> pybreaker.CircuitBreaker:
            if device_id not in fresh_breakers:
                storage = netmiko_lib.RedisCircuitBreakerStorage(f"device_{device_id}", fresh_redis)
                fresh_breakers[device_id] = pybreaker.CircuitBreaker(
                    fail_max=CIRCUIT_BREAKER_THRESHOLD,
                    reset_timeout=CIRCUIT_BREAKER_TIMEOUT,
                    name=f"device_{device_id}",
                    state_storage=storage,
                )
            return fresh_breakers[device_id]

        monkeypatch.setattr(netmiko_lib, "_get_circuit_breaker", fresh_get_circuit_breaker)

    def test_circuit_breaker_disabled(self):
        """Test that circuit breaker can be disabled."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.CIRCUIT_BREAKER_ENABLED", False):
            with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
                mock_conn = MagicMock()
                mock_conn.send_command.return_value = "output"
                mock_handler.return_value = mock_conn

                result, error = netmiko_send_command("192.168.1.1", creds, "cisco_ios", ["show version"])

                assert error is None
                assert result == {"show version": "output"}

                result, error = netmiko_send_config("192.168.1.1", creds, "cisco_ios", ["interface Gi0/1"])

                assert error is None

    def test_circuit_breaker_opens_after_failures(self):
        """Test that circuit breaker opens after threshold failures."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_handler.side_effect = netmiko.NetMikoTimeoutException("Timeout")

            # Trigger failures up to threshold - 1 (each raises)
            for _ in range(CIRCUIT_BREAKER_THRESHOLD - 1):
                with pytest.raises(netmiko.NetMikoTimeoutException):
                    netmiko_send_command("192.168.1.2", creds, "cisco_ios", ["show version"])

            # Final failure opens the circuit breaker (returns, doesn't raise)
            result, error = netmiko_send_command("192.168.1.2", creds, "cisco_ios", ["show version"])
            assert result is None
            assert "Circuit breaker open" in error

            # Subsequent calls also rejected
            result, error = netmiko_send_config("192.168.1.2", creds, "cisco_ios", ["interface Gi0/1"])
            assert result is None
            assert "Circuit breaker open" in error

    def test_circuit_breaker_per_device(self):
        """Test that circuit breakers are per-device."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            # Fail device 1 up to threshold
            mock_handler.side_effect = netmiko.NetMikoTimeoutException("Timeout")
            for _ in range(CIRCUIT_BREAKER_THRESHOLD - 1):
                with pytest.raises(netmiko.NetMikoTimeoutException):
                    netmiko_send_command("192.168.1.3", creds, "cisco_ios", ["show version"])

            # Device 1 circuit should now open
            result, error = netmiko_send_command("192.168.1.3", creds, "cisco_ios", ["show version"])
            assert "Circuit breaker open" in error

            # Device 2 should still work
            mock_conn = MagicMock()
            mock_conn.send_command.return_value = "output"
            mock_handler.side_effect = None
            mock_handler.return_value = mock_conn

            result, error = netmiko_send_command("192.168.1.4", creds, "cisco_ios", ["show version"])
            assert error is None

    def test_redis_storage_properties(self):
        """Test Redis storage class properties."""
        from naas.library.netmiko_lib import RedisCircuitBreakerStorage

        storage = RedisCircuitBreakerStorage("test_device", naas.library.netmiko_lib._redis_client)

        # Test state
        storage.state = "open"
        assert storage.state == "open"

        # Test counters
        storage.increment_counter()
        storage.increment_counter()
        assert storage.counter == 2
        storage.reset_counter()
        assert storage.counter == 0

        # Test success counter
        storage.increment_success_counter()
        assert storage.success_counter == 1
        storage.reset_success_counter()
        assert storage.success_counter == 0

        # Test opened_at
        from datetime import datetime

        now = datetime.now()
        storage.opened_at = now
        assert storage.opened_at is not None
