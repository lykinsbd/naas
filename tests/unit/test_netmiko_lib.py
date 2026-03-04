"""Unit tests for netmiko_lib functions."""

from unittest.mock import ANY, MagicMock, patch

import netmiko
from fakeredis import FakeStrictRedis
from paramiko import ssh_exception

# Must import the module first and patch _redis_client before importing the functions,
# otherwise the lazy Redis client is initialized before fakeredis is injected.
import naas.library.circuit_breaker
from naas.library.auth import Credentials

naas.library.circuit_breaker._redis_client = FakeStrictRedis()

from naas.library.circuit_breaker import RedisCircuitBreakerStorage  # noqa: E402,I001
from naas.library.netmiko_lib import _autodetect_platform, netmiko_send_command, netmiko_send_config  # noqa: E402,I001


class TestAutodetectPlatform:
    """Tests for _autodetect_platform function."""

    def test_autodetect_success(self):
        """Test successful platform detection."""
        with patch("naas.library.netmiko_lib.netmiko.SSHDetect") as mock_detect:
            mock_guesser = MagicMock()
            mock_guesser.autodetect.return_value = "cisco_nxos"
            mock_detect.return_value = mock_guesser

            platform, error = _autodetect_platform("192.168.1.1", 22, "user", "pass", "enable", "req-123")

            assert platform == "cisco_nxos"
            assert error is None

    def test_autodetect_failure(self):
        """Test platform detection failure."""
        with patch("naas.library.netmiko_lib.netmiko.SSHDetect") as mock_detect:
            mock_detect.side_effect = Exception("Connection failed")

            platform, error = _autodetect_platform("192.168.1.1", 22, "user", "pass", "enable", "req-123")

            assert platform is None
            assert "Platform autodetect failed" in error


class TestNetmikoSendCommand:
    """Tests for netmiko_send_command function."""

    def test_successful_command(self):
        """Test successful command execution."""
        creds = Credentials(username="testuser", password="testpass")
        commands = ["show version", "show interfaces"]

        with patch("naas.library.netmiko_lib.pool.get", return_value=None):
            with patch("naas.library.netmiko_lib.pool.release") as mock_release:
                with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
                    mock_conn = MagicMock()
                    mock_conn.send_command.side_effect = ["version output", "interfaces output"]
                    mock_handler.return_value = mock_conn

                    result, error = netmiko_send_command("192.168.1.1", creds, "cisco_ios", commands)

                    assert error is None
                    assert result == {"show version": "version output", "show interfaces": "interfaces output"}
                    mock_release.assert_called_once()

    def test_pool_disabled_disconnects(self):
        """When pool is disabled, connection is disconnected after use."""
        creds = Credentials(username="testuser", password="testpass")
        with patch("naas.library.netmiko_lib.CONNECTION_POOL_ENABLED", False):
            with patch("naas.library.netmiko_lib.pool.get", return_value=None):
                with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
                    mock_conn = MagicMock()
                    mock_conn.send_command.return_value = "output"
                    mock_handler.return_value = mock_conn

                    result, error = netmiko_send_command(
                        "192.168.1.1", creds, "cisco_ios", ["show version"], MagicMock()
                    )

                    assert error is None
                    mock_conn.disconnect.assert_called_once()

    def test_pool_hit(self):
        """Test that a pooled connection is reused without calling ConnectHandler."""
        creds = Credentials(username="testuser", password="testpass")
        mock_conn = MagicMock()
        mock_conn.send_command.return_value = "output"

        with patch("naas.library.netmiko_lib.pool.get", return_value=mock_conn):
            with patch("naas.library.netmiko_lib.pool.release") as mock_release:
                with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
                    result, error = netmiko_send_command("192.168.1.1", creds, "cisco_ios", ["show version"])

                    assert error is None
                    mock_handler.assert_not_called()
                    mock_release.assert_called_once()

    def test_pool_hit_bad_state_reconnects(self):
        """Test that a pooled connection in bad state triggers reconnect."""
        creds = Credentials(username="testuser", password="testpass")
        mock_conn = MagicMock()
        mock_conn.find_prompt.side_effect = Exception("stuck in sub-mode")

        with patch("naas.library.netmiko_lib.pool.get", return_value=mock_conn):
            with patch("naas.library.netmiko_lib.pool._evict"):
                with patch("naas.library.netmiko_lib.pool.release"):
                    with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
                        mock_handler.return_value.send_command.return_value = "output"
                        result, error = netmiko_send_command("192.168.1.1", creds, "cisco_ios", ["show version"])
                        assert error is None
                        mock_handler.assert_called_once()

    def test_expect_string(self):
        """Test that expect_string is passed to send_command."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.pool.get", return_value=None):
            with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
                mock_conn = MagicMock()
                mock_conn.send_command.return_value = "output"
                mock_handler.return_value = mock_conn

                result, error = netmiko_send_command(
                    "192.168.1.1", creds, "cisco_ios", ["ping 8.8.8.8"], expect_string=r"Success rate"
                )

                assert error is None
                mock_conn.send_command.assert_called_once_with(
                    "ping 8.8.8.8", read_timeout=30.0, expect_string=r"Success rate"
                )

    def test_autodetect_success(self):
        """Test platform autodetect success path."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib._autodetect_platform", return_value=("cisco_ios", None)):
            with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
                mock_conn = MagicMock()
                mock_conn.send_command.return_value = "output"
                mock_handler.return_value = mock_conn

                result, error = netmiko_send_command("192.168.1.1", creds, "autodetect", ["show version"])

                assert error is None
                assert result["_detected_platform"] == "cisco_ios"
                # Verify ConnectHandler was called with detected platform
                assert mock_handler.call_args[1]["device_type"] == "cisco_ios"

    def test_autodetect_failure(self):
        """Test platform autodetect failure path."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib._autodetect_platform", return_value=(None, "Detection failed")):
            result, error = netmiko_send_command("192.168.1.1", creds, "autodetect", ["show version"])

            assert result is None
            assert "Detection failed" in error

    def test_timeout_error(self):
        """Test timeout exception handling."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.pool.get", return_value=None):
            with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
                mock_handler.side_effect = netmiko.NetMikoTimeoutException("Connection timeout")

                result, error = netmiko_send_command("192.168.1.1", creds, "cisco_ios", ["show version"])

                assert result is None
                assert "Connection timeout" in error

    def test_auth_failure(self):
        """Test authentication failure handling."""
        creds = Credentials(username="testuser", password="wrongpass")

        with patch("naas.library.netmiko_lib.pool.get", return_value=None):
            with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
                with patch("naas.library.netmiko_lib.tacacs_auth_lockout") as mock_lockout:
                    mock_handler.side_effect = netmiko.NetMikoAuthenticationException("Auth failed")

                    result, error = netmiko_send_command(
                        "192.168.1.1", creds, "cisco_ios", ["show version"], MagicMock()
                    )

                    assert result is None
                    assert "Auth failed" in error
                    mock_lockout.assert_called_once_with(username="testuser", redis=ANY, report_failure=True)

    def test_ssh_exception(self):
        """Test SSH exception handling."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.pool.get", return_value=None):
            with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
                mock_handler.side_effect = ssh_exception.SSHException("SSH error")

                result, error = netmiko_send_command("192.168.1.1", creds, "cisco_ios", ["show version"])

                assert result is None
                assert "Unknown SSH error" in error
                assert "192.168.1.1" in error


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

            result, error = netmiko_send_config(
                "192.168.1.1", creds, "cisco_ios", commands, MagicMock(), save_config=True
            )

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

            result, error = netmiko_send_config(
                "192.168.1.1", creds, "cisco_ios", commands, MagicMock(), save_config=True
            )

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
        """Test config timeout exception handling."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_handler.side_effect = TimeoutError("Connection timeout")

            result, error = netmiko_send_config("192.168.1.1", creds, "cisco_ios", ["interface Gi0/1"])

            assert result is None
            assert "Connection timeout" in error

    def test_config_auth_failure(self):
        """Test config authentication failure handling."""
        creds = Credentials(username="testuser", password="wrongpass")

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            with patch("naas.library.netmiko_lib.tacacs_auth_lockout") as mock_lockout:
                mock_handler.side_effect = netmiko.NetMikoAuthenticationException("Auth failed")

                result, error = netmiko_send_config("192.168.1.1", creds, "cisco_ios", ["interface Gi0/1"])

                assert result is None
                assert "Auth failed" in error
                mock_lockout.assert_called_once_with(username="testuser", redis=ANY, report_failure=True)

    def test_config_value_error(self):
        """Test config ValueError handling."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_handler.side_effect = ValueError("Invalid value")

            result, error = netmiko_send_config("192.168.1.1", creds, "cisco_ios", ["interface Gi0/1"])

            assert result is None
            assert "Unknown SSH error" in error

    def test_config_invalid_exception(self):
        """Test that ConfigInvalidException is returned as error without raising."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
            mock_handler.return_value.send_config_set.side_effect = netmiko.ConfigInvalidException("% Invalid input")

            result, error = netmiko_send_config("192.168.1.1", creds, "cisco_ios", ["bad command"])

            assert result is None
            assert "% Invalid input" in error


class TestCircuitBreaker:
    """Tests for circuit breaker functionality."""

    def test_circuit_breaker_disabled(self):
        """Test that circuit breaker can be disabled."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.CIRCUIT_BREAKER_ENABLED", False):
            with patch("naas.library.netmiko_lib.pool.get", return_value=None):
                with patch("naas.library.netmiko_lib.pool.release"):
                    with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
                        mock_conn = MagicMock()
                        mock_conn.send_command.return_value = "output"
                        mock_handler.return_value = mock_conn

                        result, error = netmiko_send_command(
                            "192.168.1.1", creds, "cisco_ios", ["show version"], MagicMock()
                        )

                        assert error is None
                        assert result == {"show version": "output"}

                        result, error = netmiko_send_config(
                            "192.168.1.1", creds, "cisco_ios", ["interface Gi0/1"], MagicMock()
                        )

                        assert error is None

    def test_circuit_breaker_opens_after_failures(self):
        """Test that circuit breaker opens after threshold failures."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.pool.get", return_value=None):
            with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
                mock_handler.side_effect = netmiko.NetMikoTimeoutException("Timeout")

                # Trigger failures up to threshold
                for _ in range(5):
                    result, error = netmiko_send_command(
                        "192.168.1.2", creds, "cisco_ios", ["show version"], MagicMock()
                    )
                    assert result is None

                # Next call should be rejected by circuit breaker
                result, error = netmiko_send_command("192.168.1.2", creds, "cisco_ios", ["show version"])
                assert result is None
                assert "Circuit breaker open" in error

                # Test send_config too
                result, error = netmiko_send_config("192.168.1.2", creds, "cisco_ios", ["interface Gi0/1"])
                assert result is None
                assert "Circuit breaker open" in error

    def test_circuit_breaker_per_device(self):
        """Test that circuit breakers are per-device."""
        creds = Credentials(username="testuser", password="testpass")

        with patch("naas.library.netmiko_lib.pool.get", return_value=None):
            with patch("naas.library.netmiko_lib.pool.release"):
                with patch("naas.library.netmiko_lib.netmiko.ConnectHandler") as mock_handler:
                    # Fail device 1
                    mock_handler.side_effect = netmiko.NetMikoTimeoutException("Timeout")
                    for _ in range(5):
                        netmiko_send_command("192.168.1.3", creds, "cisco_ios", ["show version"])

                    # Device 1 circuit should be open
                    result, error = netmiko_send_command(
                        "192.168.1.3", creds, "cisco_ios", ["show version"], MagicMock()
                    )
                    assert "Circuit breaker open" in error

                    # Device 2 should still work
                    mock_conn = MagicMock()
                    mock_conn.send_command.return_value = "output"
                    mock_handler.side_effect = None
                    mock_handler.return_value = mock_conn

                    result, error = netmiko_send_command(
                        "192.168.1.4", creds, "cisco_ios", ["show version"], MagicMock()
                    )
                    assert error is None

    def test_redis_storage_properties(self):
        """Test Redis storage class properties."""
        storage = RedisCircuitBreakerStorage("test_device", naas.library.circuit_breaker._redis_client)

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
