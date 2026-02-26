#!/usr/bin/env python3

"""
Library to abstract Netmiko functions for use by the NAAS API.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import netmiko
import pybreaker
from paramiko import ssh_exception  # type: ignore[import-untyped]
from redis import Redis

from naas.config import (
    CIRCUIT_BREAKER_ENABLED,
    CIRCUIT_BREAKER_THRESHOLD,
    CIRCUIT_BREAKER_TIMEOUT,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
)
from naas.library.auth import tacacs_auth_lockout

if TYPE_CHECKING:
    from collections.abc import Sequence

    from naas.library.auth import Credentials


logger = logging.getLogger(name="NAAS")


class RedisCircuitBreakerStorage(pybreaker.CircuitBreakerStorage):
    """Redis-backed storage for circuit breaker state shared across workers."""

    def __init__(self, name: str, redis_client: Redis):
        super().__init__(name)
        self.redis = redis_client
        self._key = f"circuit_breaker:{name}"

    @property
    def state(self) -> str:
        """Get current circuit state."""
        return self.redis.hget(self._key, "state") or "closed"

    @state.setter
    def state(self, state: str) -> None:
        """Set current circuit state."""
        self.redis.hset(self._key, "state", state)

    def increment_counter(self) -> None:
        """Increment failure counter."""
        self.redis.hincrby(self._key, "counter", 1)

    def reset_counter(self) -> None:
        """Reset failure counter."""
        self.redis.hset(self._key, "counter", 0)

    def increment_success_counter(self) -> None:
        """Increment success counter."""
        self.redis.hincrby(self._key, "success_counter", 1)

    def reset_success_counter(self) -> None:
        """Reset success counter."""
        self.redis.hset(self._key, "success_counter", 0)

    @property
    def counter(self) -> int:
        """Get failure counter."""
        val = self.redis.hget(self._key, "counter")
        return int(val) if val else 0

    @property
    def success_counter(self) -> int:
        """Get success counter."""
        val = self.redis.hget(self._key, "success_counter")
        return int(val) if val else 0

    @property
    def opened_at(self) -> datetime | None:
        """Get when circuit was opened."""
        val = self.redis.hget(self._key, "opened_at")
        return datetime.fromisoformat(val) if val else None

    @opened_at.setter
    def opened_at(self, dt: datetime) -> None:
        """Set when circuit was opened."""
        self.redis.hset(self._key, "opened_at", dt.isoformat())


# Redis client for circuit breaker storage
_redis_client = Redis(host=REDIS_HOST, port=int(REDIS_PORT), password=REDIS_PASSWORD, decode_responses=True)

# Per-device circuit breakers
_circuit_breakers: dict[str, pybreaker.CircuitBreaker] = {}


def _get_circuit_breaker(device_id: str) -> pybreaker.CircuitBreaker:
    """Get or create a circuit breaker for a specific device."""
    if device_id not in _circuit_breakers:
        storage = RedisCircuitBreakerStorage(f"device_{device_id}", _redis_client)
        _circuit_breakers[device_id] = pybreaker.CircuitBreaker(
            fail_max=CIRCUIT_BREAKER_THRESHOLD,
            reset_timeout=CIRCUIT_BREAKER_TIMEOUT,
            name=f"device_{device_id}",
            state_storage=storage,
        )
    return _circuit_breakers[device_id]


def netmiko_send_command(
    ip: str,
    credentials: "Credentials",
    device_type: str,
    commands: "Sequence[str]",
    port: int = 22,
    delay_factor: int = 1,
    verbose: bool = False,
    request_id: str = "",
) -> "tuple[dict | None, str | None]":
    """
    Instantiate a netmiko wrapper instance, feed me an IP, Platform Type, Username, Password, any commands to run.

    :param ip: What IP are we connecting to?
    :param credentials: A naas.library.auth.Credentials object with the username/password/enable in it
    :param commands: List of the commands to issue to the device
    :param device_type: What Netmiko device type are we connecting to?
    :param port: What TCP Port are we connecting to?
    :param delay_factor: Netmiko delay factor, default of 1, higher is slower but more reliable on laggy links
    :param verbose: Turn on Netmiko verbose logging
    :param request_id: Correlation ID from the originating API request for end-to-end log tracing
    :return: A Tuple of a dict of the results (if any) and a string describing the error (if any)
    """
    if CIRCUIT_BREAKER_ENABLED:
        breaker = _get_circuit_breaker(ip)
        try:
            return breaker.call(  # type: ignore[no-any-return]
                _netmiko_send_command_impl,
                ip,
                credentials,
                device_type,
                commands,
                port,
                delay_factor,
                verbose,
                request_id,
            )
        except pybreaker.CircuitBreakerError:
            logger.warning("%s %s:Circuit breaker open, rejecting connection attempt", request_id, ip)
            return None, f"Circuit breaker open for device {ip} - too many recent failures"
        except (TimeoutError, netmiko.NetMikoTimeoutException) as e:
            return None, str(e)
        except (ssh_exception.SSHException, ValueError) as e:
            return None, f"Unknown SSH error connecting to device {ip}: {str(e)}"
    else:
        return _netmiko_send_command_impl(
            ip, credentials, device_type, commands, port, delay_factor, verbose, request_id
        )


def _netmiko_send_command_impl(
    ip: str,
    credentials: "Credentials",
    device_type: str,
    commands: "Sequence[str]",
    port: int = 22,
    delay_factor: int = 1,
    verbose: bool = False,
    request_id: str = "",
) -> "tuple[dict | None, str | None]":
    # Create device dict to pass netmiko
    netmiko_device = {
        "device_type": device_type,
        "ip": ip,
        "username": credentials.username,
        "password": credentials.password,
        "secret": credentials.enable,
        "port": port,
        "ssh_config_file": "/app/naas/ssh_config",
        "allow_agent": False,
        "use_keys": False,
        "verbose": verbose,
    }

    try:
        logger.debug("%s %s:Establishing connection...", request_id, ip)
        net_connect = netmiko.ConnectHandler(**netmiko_device)

        net_output = {}
        for command in commands:
            logger.debug("%s %s:Sending %s", request_id, ip, command)
            net_output[command] = net_connect.send_command(command, delay_factor=delay_factor)

        # Perform graceful disconnection of this SSH session
        net_connect.disconnect()

    except (TimeoutError, netmiko.NetMikoTimeoutException) as e:
        logger.debug("%s %s:Netmiko timed out connecting to device: %s", request_id, ip, e)
        raise  # Re-raise to trigger circuit breaker
    except netmiko.NetMikoAuthenticationException as e:
        logger.debug("%s %s:Netmiko authentication failure connecting to device: %s", request_id, ip, e)
        tacacs_auth_lockout(username=credentials.username, report_failure=True)
        return None, str(e)  # Don't trigger circuit breaker for auth failures
    except (ssh_exception.SSHException, ValueError) as e:
        logger.debug("%s %s:Netmiko cannot connect to device: %s", request_id, ip, e)
        raise  # Re-raise to trigger circuit breaker

    logger.debug("%s %s:Netmiko executed successfully.", request_id, ip)
    return net_output, None


def netmiko_send_config(
    ip: str,
    credentials: "Credentials",
    device_type: str,
    commands: "Sequence[str]",
    port: int = 22,
    save_config: bool = False,
    commit: bool = False,
    delay_factor: int = 1,
    verbose: bool = False,
    request_id: str = "",
) -> "tuple[dict | None, str | None]":
    """
    Instantiate a netmiko wrapper instance, feed me an IP, Platform Type, Username, Password, any commands to run.

    :param ip: What IP are we connecting to?
    :param credentials: A naas.library.auth.Credentials object with the username/password/enable in it
    :param commands: List of the commands to issue to the device
    :param device_type: What Netmiko device type are we connecting to?
    :param port: What TCP Port are we connecting to?
    :param save_config: Do you want to save this configuration upon insertion?  Default: False, don't save the config
    :param commit: Do you want to commit this candidate configuration to the running config?  Default: False
    :param delay_factor: Netmiko delay factor, default of 1, higher is slower but more reliable on laggy links
    :param verbose: Turn on Netmiko verbose logging
    :param request_id: Correlation ID from the originating API request for end-to-end log tracing
    :return: A Tuple of a dict of the results (if any) and a string describing the error (if any)
    """
    if CIRCUIT_BREAKER_ENABLED:
        breaker = _get_circuit_breaker(ip)
        try:
            return breaker.call(  # type: ignore[no-any-return]
                _netmiko_send_config_impl,
                ip,
                credentials,
                device_type,
                commands,
                port,
                save_config,
                commit,
                delay_factor,
                verbose,
                request_id,
            )
        except pybreaker.CircuitBreakerError:
            logger.warning("%s %s:Circuit breaker open, rejecting connection attempt", request_id, ip)
            return None, f"Circuit breaker open for device {ip} - too many recent failures"
        except (TimeoutError, netmiko.NetMikoTimeoutException) as e:
            return None, str(e)
        except (ssh_exception.SSHException, ValueError) as e:
            return None, f"Unknown SSH error connecting to device {ip}: {str(e)}"
    else:
        return _netmiko_send_config_impl(
            ip, credentials, device_type, commands, port, save_config, commit, delay_factor, verbose, request_id
        )


def _netmiko_send_config_impl(
    ip: str,
    credentials: "Credentials",
    device_type: str,
    commands: "Sequence[str]",
    port: int = 22,
    save_config: bool = False,
    commit: bool = False,
    delay_factor: int = 1,
    verbose: bool = False,
    request_id: str = "",
) -> "tuple[dict | None, str | None]":
    # Create device dict to pass netmiko
    netmiko_device = {
        "device_type": device_type,
        "ip": ip,
        "username": credentials.username,
        "password": credentials.password,
        "secret": credentials.enable,
        "port": port,
        "ssh_config_file": "/app/naas/ssh_config",
        "allow_agent": False,
        "use_keys": False,
        "verbose": verbose,
    }

    try:
        logger.debug("%s %s:Establishing connection...", request_id, ip)
        net_connect = netmiko.ConnectHandler(**netmiko_device)

        net_output = {}
        logger.debug("%s %s:Sending config_set: %s", request_id, ip, commands)
        net_output["config_set_output"] = net_connect.send_config_set(commands, delay_factor=delay_factor)

        if save_config:
            try:
                logger.debug("%s %s: Saving configuration", request_id, ip)
                net_connect.save_config()
            except NotImplementedError:
                logger.debug(
                    "%s %s: This device_type (%s) does not support the save_config operation.",
                    request_id,
                    ip,
                    device_type,
                )

        if commit:
            try:
                logger.debug("%s %s: Committing configuration", request_id, ip)
                net_connect.commit()
            except AttributeError:
                logger.debug(
                    "%s %s: This device_type (%s) does not support the commit operation", request_id, ip, device_type
                )

        # Perform graceful disconnection of this SSH session
        net_connect.disconnect()

    except (TimeoutError, netmiko.NetMikoTimeoutException) as e:
        logger.debug("%s %s:Netmiko timed out connecting to device: %s", request_id, ip, e)
        raise  # Re-raise to trigger circuit breaker
    except netmiko.NetMikoAuthenticationException as e:
        logger.debug("%s %s:Netmiko authentication failure connecting to device: %s", request_id, ip, e)
        tacacs_auth_lockout(username=credentials.username, report_failure=True)
        return None, str(e)  # Don't trigger circuit breaker for auth failures
    except (ssh_exception.SSHException, ValueError) as e:
        logger.debug("%s %s:Netmiko cannot connect to device: %s", request_id, ip, e)
        raise  # Re-raise to trigger circuit breaker

    logger.debug("%s %s:Netmiko executed successfully.", request_id, ip)
    return net_output, None
