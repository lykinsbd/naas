# NAAS
Netmiko As A Service

This is a Python/Flask based REST API wrapper for the
[Netmiko](https://github.com/ktbyers/netmiko) Python libray.

NAAS provides the following benefits:
1. Allows you to create a centralized location which has access
 to the network equipment, and allow users from outside that protected
 bastion to access network resources. This is useful in large networks
 where many consumers or orchestration tools may need to talk to the
 network devices, but you wish to maintain only a few allowed hosts on
 the network equipment.
2. Creates a semi-RESTful interface for networking equipment that does
 not have one.