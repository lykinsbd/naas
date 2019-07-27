# NAAS
Netmiko As A Service

This is a web-based API wrapper for the [Netmiko](https://github.com/ktbyers/netmiko) Python library.

It is built in Python utilizing Flask/RQ, and utilizes Redis for the job queueing.

* [NAAS API Documentation](https://lykinsbd.github.io/naas)


## Running NAAS

There are several deployement scenarios for NAAS,
 the "batteries included" deployment is described briefly below:

* Install Docker on a server that has access to your network devices
* Join that host to (or initialize) a Docker Swarm
* Clone the repo down from Github
* Execute the following:
    * ```docker stack deploy --compose-file docker-compose.yml naas```
* Validate that your service has deployed:
    * ```docker stack ps naas```
    * You should see 4 containers in the `Running` state:
        1. naas_api.1
        2. naas_worker.1
        3. naas_worker.2
        4. naas_redis.1
* Perform an HTTP GET to `https://<your_server_ip>:5000/healthcheck` and look for a 200 response.

----

NAAS provides the following benefits:
1. Allows you to create a centralized location which has access
 to the network equipment, and allow users from outside that protected
 bastion to access network resources. This is useful in large networks
 where many consumers or orchestration tools may need to talk to the
 network devices, but you wish to maintain only a few allowed hosts on
 the network equipment.
2. Creates a semi-RESTful interface for networking equipment that does
 not have one.