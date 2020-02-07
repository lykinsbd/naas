#!/usr/bin/env python3

"""
Library to abstract Netmiko functions for use by the NAAS API.
"""

import logging
import netmiko

from naas.library.auth import tacacs_auth_lockout
from paramiko import ssh_exception
from socket import timeout
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Optional, Sequence, Tuple
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
) -> "Tuple[Optional[dict], Optional[str]]":

    """
    Instantiate a netmiko wrapper instance, feed me an IP, Platform Type, Username, Password, any commands to run.

    :param ip: What IP are we connecting to?
    :param credentials: A naas.library.auth.Credentials object with the username/password/enable in it
    :param commands: List of the commands to issue to the device
    :param device_type: What Netmiko device type are we connecting to?
    :param port: What TCP Port are we connecting to?
    :param delay_factor: Netmiko delay factor, default of 1, higher is slower but more reliable on laggy links
    :param verbose: Turn on Netmiko verbose logging
    :return: A Tuple of a dict of the results (if any) and a string describing the error (if any)
    """

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
        logger.debug("%s:Establishing connection...", ip)
        net_connect = netmiko.ConnectHandler(**netmiko_device)

        net_output = {}
        for command in commands:
            logger.debug("%s:Sending %s", ip, command)
            net_output[command] = net_connect.send_command(command, delay_factor=delay_factor)

        # Perform graceful disconnection of this SSH session
        net_connect.disconnect()

    except (netmiko.NetMikoTimeoutException, timeout) as e:
        logger.debug("%s:Netmiko timed out connecting to device: %s", ip, e)
        return None, str(e)
    except netmiko.NetMikoAuthenticationException as e:
        logger.debug("%s:Netmiko authentication failure connecting to device: %s", ip, e)
        tacacs_auth_lockout(username=credentials.username, report_failure=True)
        return None, str(e)
    except (ssh_exception.SSHException, ValueError) as e:
        logger.debug("%s:Netmiko cannot connect to device: %s", ip, e)
        return None, ("Unknown SSH error connecting to device {0}: {1}".format(ip, str(e)))

    logger.debug("%s:Netmiko executed successfully.", ip)
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
) -> "Tuple[Optional[dict], Optional[str]]":

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
    :return: A Tuple of a dict of the results (if any) and a string describing the error (if any)
    """

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
        logger.debug("%s:Establishing connection...", ip)
        net_connect = netmiko.ConnectHandler(**netmiko_device)

        net_output = {}
        logger.debug("%s:Sending config_set: %s", ip, commands)
        net_output["config_set_output"] = net_connect.send_config_set(commands, delay_factor=delay_factor)

        if save_config:
            try:
                logger.debug("%s: Saving configuration", ip)
                net_connect.save_config()
            except NotImplementedError:
                logger.debug("%s: This device_type (%s) does not support the save_config operation.", ip, device_type)

        if commit:
            try:
                logger.debug("%s: Committing configuration", ip)
                net_connect.commit()
            except AttributeError:
                logger.debug("%s: This device_type (%s) does not support the commit operation", ip, device_type)

        # Perform graceful disconnection of this SSH session
        net_connect.disconnect()

    except (netmiko.NetMikoTimeoutException, timeout) as e:
        logger.debug("%s:Netmiko timed out connecting to device: %s", ip, e)
        return None, str(e)
    except netmiko.NetMikoAuthenticationException as e:
        logger.debug("%s:Netmiko authentication failure connecting to device: %s", ip, e)
        tacacs_auth_lockout(username=credentials.username, report_failure=True)
        return None, str(e)
    except (ssh_exception.SSHException, ValueError) as e:
        logger.debug("%s:Netmiko cannot connect to device: %s", ip, e)
        return None, ("Unknown SSH error connecting to device {0}: {1}".format(ip, str(e)))

    logger.debug("%s:Netmiko executed successfully.", ip)
    return net_output, None
