#!/usr/bin/env python3

"""
Library to abstract Netmiko functions for use by the NAAS API.
"""

import logging
import netmiko

from paramiko import ssh_exception
from socket import timeout
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Optional, Sequence, Tuple


logger = logging.getLogger(name="NAAS")


class NetmikoWrapper(object):
    """
    Wrapper for Netmiko interactions that is exposed to the API
    """

    def __init__(
        self,
        ip: str,
        username: str,
        password: str,
        platform: str,
        commands: "Sequence[str]",
        port: int = 22,
        enable: "Optional[str]" = None,
        config_set: bool = False,
        delay_factor: int = 2,
        verbose: bool = False,
    ) -> None:

        """
        Instantiate a netmiko wrapper instance, feed me an IP, Platform Type, Username, Password, Config Set bool, and
        then any commands to run.

        :param ip: What IP are we connecting to?
        :param username: What is the username for this connection?
        :param password: What is the password?
        :param commands: List of the commands to issue to the device
        :param platform: What Netmiko platform type are we connecting to?
        :param port: What TCP Port are we connecting to?
        :param enable: If this device requires a second auth/Enable password, what is it?
        :param config_set: Is this a set of config changes, or a list of individual commands?
        :param delay_factor: Netmiko delay factor, default of 2, higher is slower but more reliable on laggy links
        :param verbose: Turn on Netmiko verbose logging
        """

        # Setup any needed enable password if not provided.
        if not enable:
            enable = password

        self.config_set = config_set
        self.commands = commands
        self.delay_factor = delay_factor

        # Create device dict to pass netmiko
        self.netmiko_device = {
            "device_type": platform,
            "ip": ip,
            "username": username,
            "password": password,
            "secret": enable,
            "port": port,
            "ssh_config_file": "/app/naas/ssh_config",
            "allow_agent": False,
            "use_keys": False,
            "verbose": verbose,
        }

    def send_commands(self) -> "Tuple[Optional[dict], Optional[str]]":
        """
        Send given command list or config set to device
        :return: A Tuple containing any output in a dict or any error in a string
        """

        try:
            logger.debug("%s:Establishing connection...", self.netmiko_device["ip"])
            net_connect = netmiko.ConnectHandler(**self.netmiko_device)

            net_output = {}
            if self.config_set:
                logger.debug("%s:Sending config_set: %s", self.netmiko_device["ip"], self.commands)
                net_output["config_set_output"] = net_connect.send_config_set(
                    self.commands, delay_factor=self.delay_factor
                )
            else:
                for command in self.commands:
                    logger.debug("%s:Sending %s", self.netmiko_device["ip"], command)
                    net_output[command] = net_connect.send_command(command, delay_factor=self.delay_factor)

            net_connect.disconnect()

        except (netmiko.NetMikoTimeoutException, timeout) as e:
            logger.debug("%s:Netmiko cannot connect to device: %s", self.netmiko_device["ip"], e)
            return None, str(e)
        except netmiko.NetMikoAuthenticationException as e:
            logger.debug("%s:Netmiko cannot connect to device: %s", self.netmiko_device["ip"], e)
            return None, str(e)
        except (ssh_exception.SSHException, ValueError) as e:
            logger.debug("%s:Netmiko cannot connect to device: %s", self.netmiko_device["ip"], e)
            return None, ("Unknown SSH error connecting to device {0}: {1}".format(self.netmiko_device["ip"], str(e)))

        logger.debug("%s:Netmiko executed successfully.", self.netmiko_device["ip"])
        return net_output, None
