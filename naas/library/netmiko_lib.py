#!/usr/bin/env python3


"""
Library to abstract Netmiko functions for use by the NAAS API.
"""

import logging
import time
from typing import TYPE_CHECKING

import netmiko
from paramiko import ssh_exception

from naas.config import CIRCUIT_BREAKER_ENABLED, CONNECTION_POOL_ENABLED, CONNECTION_POOL_KEEPALIVE
from naas.library.audit import emit_audit_event
from naas.library.auth import tacacs_auth_lockout
from naas.library.circuit_breaker import _get_redis, with_circuit_breaker
from naas.library.connection_pool import pool

# Common error patterns across IOS, NX-OS, EOS, JunOS, and similar platforms
_CONFIG_ERROR_PATTERN = r"(?i)(% invalid|% incomplete|% ambiguous|% error|error:|invalid input|syntax error)"


def _autodetect_platform(
    ip: str, port: int, username: str, password: str, enable: str, request_id: str
) -> tuple[str | None, str | None]:
    """
    Use SSHDetect to fingerprint device platform.

    Returns:
        (detected_platform, error_string) — one will be None
    """
    try:
        logger.debug("%s %s:Running SSHDetect...", request_id, ip)
        guesser = netmiko.SSHDetect(
            device_type="autodetect",
            ip=ip,
            port=port,
            username=username,
            password=password,
            secret=enable,
        )
        best_match = guesser.autodetect()
        logger.debug("%s %s:Detected platform: %s", request_id, ip, best_match)
        return best_match, None
    except Exception as e:
        logger.debug("%s %s:SSHDetect failed: %s", request_id, ip, e)
        return None, f"Platform autodetect failed: {str(e)}"


if TYPE_CHECKING:
    from collections.abc import Sequence

    from naas.library.auth import Credentials


logger = logging.getLogger(name="NAAS")


def netmiko_send_command(
    ip: str,
    credentials: "Credentials",
    device_type: str,
    commands: "Sequence[str]",
    port: int = 22,
    read_timeout: float = 30.0,
    expect_string: str | None = None,
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
    :param read_timeout: Read timeout in seconds for device responses
    :param expect_string: Regex pattern to match in device output (overrides prompt detection)
    :param verbose: Turn on Netmiko verbose logging
    :param request_id: Correlation ID from the originating API request for end-to-end log tracing
    :return: A Tuple of a dict of the results (if any) and a string describing the error (if any)
    """
    if CIRCUIT_BREAKER_ENABLED:
        return with_circuit_breaker(  # type: ignore[no-any-return]  # pybreaker has no stubs; with_circuit_breaker returns Any
            ip,
            request_id,
            _netmiko_send_command_impl,
            ip,
            credentials,
            device_type,
            commands,
            port,
            read_timeout,
            expect_string,
            verbose,
            request_id,
        )
    return _netmiko_send_command_impl(
        ip, credentials, device_type, commands, port, read_timeout, expect_string, verbose, request_id
    )


def _netmiko_send_command_impl(
    ip: str,
    credentials: "Credentials",
    device_type: str,
    commands: "Sequence[str]",
    port: int = 22,
    read_timeout: float = 30.0,
    expect_string: str | None = None,
    verbose: bool = False,
    request_id: str = "",
) -> "tuple[dict | None, str | None]":
    start_time = time.time()

    # Handle platform autodetect
    detected_platform = None
    if device_type == "autodetect":
        device_type_result, error = _autodetect_platform(
            ip, port, credentials.username, credentials.password, credentials.enable, request_id
        )
        if error is not None:
            duration_ms = int((time.time() - start_time) * 1000)
            emit_audit_event("job.completed", request_id=request_id, status="failed", duration_ms=duration_ms)
            return None, error
        device_type = device_type_result  # type: ignore[assignment]  # autodetect guarantees non-None on success
        detected_platform = device_type

    # Skip pool for autodetect — can't pool without knowing platform upfront
    use_pool = CONNECTION_POOL_ENABLED and detected_platform is None

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
        "fast_cli": True,
        "verbose": verbose,
    }

    try:
        net_connect = None

        if use_pool:
            net_connect = pool.get(ip, port, credentials.username, credentials.password, device_type)

        if net_connect is None:
            logger.debug("%s %s:Establishing connection...", request_id, ip)
            netmiko_device["keepalive"] = CONNECTION_POOL_KEEPALIVE if use_pool else 0
            net_connect = netmiko.ConnectHandler(**netmiko_device)
        else:
            # Verify pooled connection is at a clean prompt before use
            try:
                net_connect.find_prompt()
            except Exception:
                logger.debug("%s %s:Pooled connection in bad state, reconnecting", request_id, ip)
                pool._evict((ip, port, pool._cred_hash(credentials.username, credentials.password), device_type))
                netmiko_device["keepalive"] = CONNECTION_POOL_KEEPALIVE
                net_connect = netmiko.ConnectHandler(**netmiko_device)

        net_output = {}
        for command in commands:
            logger.debug("%s %s:Sending %s", request_id, ip, command)
            kwargs: dict[str, float | str] = {"read_timeout": read_timeout}
            if expect_string is not None:
                kwargs["expect_string"] = expect_string
            net_output[command] = net_connect.send_command(command, **kwargs)

        if use_pool:
            pool.release(ip, port, credentials.username, credentials.password, device_type, net_connect)
        else:
            net_connect.disconnect()

    except (TimeoutError, netmiko.NetMikoTimeoutException) as e:
        logger.debug("%s %s:Netmiko timed out connecting to device: %s", request_id, ip, e)
        duration_ms = int((time.time() - start_time) * 1000)
        emit_audit_event("job.completed", request_id=request_id, status="failed", duration_ms=duration_ms)
        raise  # Re-raise to trigger circuit breaker
    except netmiko.NetMikoAuthenticationException as e:
        logger.debug("%s %s:Netmiko authentication failure connecting to device: %s", request_id, ip, e)
        tacacs_auth_lockout(username=credentials.username, redis=_get_redis(), report_failure=True)
        duration_ms = int((time.time() - start_time) * 1000)
        emit_audit_event("job.completed", request_id=request_id, status="failed", duration_ms=duration_ms)
        return None, str(e)  # Don't trigger circuit breaker for auth failures
    except (ssh_exception.SSHException, ValueError) as e:
        logger.debug("%s %s:Netmiko cannot connect to device: %s", request_id, ip, e)
        duration_ms = int((time.time() - start_time) * 1000)
        emit_audit_event("job.completed", request_id=request_id, status="failed", duration_ms=duration_ms)
        raise  # Re-raise to trigger circuit breaker

    logger.debug("%s %s:Netmiko executed successfully.", request_id, ip)
    duration_ms = int((time.time() - start_time) * 1000)
    emit_audit_event("job.completed", request_id=request_id, status="finished", duration_ms=duration_ms)

    # Include detected_platform in results if autodetect was used
    if detected_platform is not None:
        net_output["_detected_platform"] = detected_platform

    return net_output, None


def netmiko_send_config(
    ip: str,
    credentials: "Credentials",
    device_type: str,
    commands: "Sequence[str]",
    port: int = 22,
    save_config: bool = False,
    commit: bool = False,
    read_timeout: float = 30.0,
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
    :param read_timeout: Read timeout in seconds for device responses
    :param verbose: Turn on Netmiko verbose logging
    :param request_id: Correlation ID from the originating API request for end-to-end log tracing
    :return: A Tuple of a dict of the results (if any) and a string describing the error (if any)
    """
    if CIRCUIT_BREAKER_ENABLED:
        return with_circuit_breaker(  # type: ignore[no-any-return]  # pybreaker has no stubs; with_circuit_breaker returns Any
            ip,
            request_id,
            _netmiko_send_config_impl,
            ip,
            credentials,
            device_type,
            commands,
            port,
            save_config,
            commit,
            read_timeout,
            verbose,
            request_id,
        )
    return _netmiko_send_config_impl(
        ip, credentials, device_type, commands, port, save_config, commit, read_timeout, verbose, request_id
    )


def _netmiko_send_config_impl(
    ip: str,
    credentials: "Credentials",
    device_type: str,
    commands: "Sequence[str]",
    port: int = 22,
    save_config: bool = False,
    commit: bool = False,
    read_timeout: float = 30.0,
    verbose: bool = False,
    request_id: str = "",
) -> "tuple[dict | None, str | None]":
    start_time = time.time()
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
        "fast_cli": True,
        "verbose": verbose,
    }

    try:
        logger.debug("%s %s:Establishing connection...", request_id, ip)
        net_connect = netmiko.ConnectHandler(**netmiko_device)

        net_output = {}
        logger.debug("%s %s:Sending config_set: %s", request_id, ip, commands)
        net_output["config_set_output"] = net_connect.send_config_set(
            commands, read_timeout=read_timeout, error_pattern=_CONFIG_ERROR_PATTERN
        )

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

        net_connect.disconnect()

    except netmiko.ConfigInvalidException as e:
        logger.debug("%s %s:Config rejected by device: %s", request_id, ip, e)
        duration_ms = int((time.time() - start_time) * 1000)
        emit_audit_event("job.completed", request_id=request_id, status="failed", duration_ms=duration_ms)
        return None, str(e)  # Config error — do not trigger circuit breaker
    except (TimeoutError, netmiko.NetMikoTimeoutException) as e:
        logger.debug("%s %s:Netmiko timed out connecting to device: %s", request_id, ip, e)
        duration_ms = int((time.time() - start_time) * 1000)
        emit_audit_event("job.completed", request_id=request_id, status="failed", duration_ms=duration_ms)
        raise  # Re-raise to trigger circuit breaker
    except netmiko.NetMikoAuthenticationException as e:
        logger.debug("%s %s:Netmiko authentication failure connecting to device: %s", request_id, ip, e)
        tacacs_auth_lockout(username=credentials.username, redis=_get_redis(), report_failure=True)
        duration_ms = int((time.time() - start_time) * 1000)
        emit_audit_event("job.completed", request_id=request_id, status="failed", duration_ms=duration_ms)
        return None, str(e)  # Don't trigger circuit breaker for auth failures
    except (ssh_exception.SSHException, ValueError) as e:
        logger.debug("%s %s:Netmiko cannot connect to device: %s", request_id, ip, e)
        duration_ms = int((time.time() - start_time) * 1000)
        emit_audit_event("job.completed", request_id=request_id, status="failed", duration_ms=duration_ms)
        raise  # Re-raise to trigger circuit breaker

    logger.debug("%s %s:Netmiko executed successfully.", request_id, ip)
    duration_ms = int((time.time() - start_time) * 1000)
    emit_audit_event("job.completed", request_id=request_id, status="finished", duration_ms=duration_ms)
    return net_output, None
