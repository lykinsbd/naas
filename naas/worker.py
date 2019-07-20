# RQ Worker to handle netmiko connections

from naas.config import REDIS_HOST, REDIS_PORT
from naas.library.netmiko_lib import netmiko_send_command
