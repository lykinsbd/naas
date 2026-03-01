#!/usr/bin/env python3


"""
Library to abstract Netmiko functions for use by the NAAS API.
"""

import logging
import time
from typing import TYPE_CHECKING

import netmiko
from paramiko import ssh_exception

from naas.config import CIRCUIT_BREAKER_ENABLED
from naas.library.audit import emit_audit_event
from naas.library.auth import tacacs_auth_lockout
from naas.library.circuit_breaker import with_circuit_breaker

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
        return with_circuit_breaker(  # type: ignore[no-any-return]  # pybreaker has no stubs; with_circuit_breaker returns Any
            ip,
            request_id,
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
    return _netmiko_send_command_impl(ip, credentials, device_type, commands, port, delay_factor, verbose, request_id)


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
        "verbose": verbose,
    }

    try:
        logger.debug("%s %s:Establishing connection...", request_id, ip)
        net_connect = netmiko.ConnectHandler(**netmiko_device)

        net_output = {}
        for command in commands:
            logger.debug("%s %s:Sending %s", request_id, ip, command)
            net_output[command] = net_connect.send_command(command, delay_factor=delay_factor)

        net_connect.disconnect()

    except (TimeoutError, netmiko.NetMikoTimeoutException) as e:
        logger.debug("%s %s:Netmiko timed out connecting to device: %s", request_id, ip, e)
        duration_ms = int((time.time() - start_time) * 1000)
        emit_audit_event("job.completed", request_id=request_id, status="failed", duration_ms=duration_ms)
        raise  # Re-raise to trigger circuit breaker
    except netmiko.NetMikoAuthenticationException as e:
        logger.debug("%s %s:Netmiko authentication failure connecting to device: %s", request_id, ip, e)
        tacacs_auth_lockout(username=credentials.username, report_failure=True)
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
            delay_factor,
            verbose,
            request_id,
        )
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

        net_connect.disconnect()

    except (TimeoutError, netmiko.NetMikoTimeoutException) as e:
        logger.debug("%s %s:Netmiko timed out connecting to device: %s", request_id, ip, e)
        duration_ms = int((time.time() - start_time) * 1000)
        emit_audit_event("job.completed", request_id=request_id, status="failed", duration_ms=duration_ms)
        raise  # Re-raise to trigger circuit breaker
    except netmiko.NetMikoAuthenticationException as e:
        logger.debug("%s %s:Netmiko authentication failure connecting to device: %s", request_id, ip, e)
        tacacs_auth_lockout(username=credentials.username, report_failure=True)
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
