# NAAS
Netmiko As A Service

NAAS is a web-based REST API wrapper for the widely-used [Netmiko](https://github.com/ktbyers/netmiko)
 Python library.  Netmiko provides structured methods for interacting with Network Devices via SSH/Telnet.


NAAS then wraps those Netmiko methods in a RESTful API interface to provide an interface
 for other automation tools (or users) to consume.

NAAS is written in Python, and utilizes the following libraries/technologies:
    
* [Netmiko](https://github.com/ktbyers/netmiko) for connectivity to network devices
* [Flask](https://github.com/pallets/flask) for the service/API framework
* [Flask-RESTful](https://github.com/flask-restful/flask-restful) to simplify the REST API structure
* [Gunicorn](https://github.com/benoitc/gunicorn) for the HTTP server
* [RQ](https://github.com/rq/rq) for the background job queueing/execution framework
* [Redis](https://github.com/antirez/redis) for job queueing and other backend K/V store functions

Online API documentation can be found here: [NAAS API Documentation](https://lykinsbd.github.io/naas)

## Why Use NAAS?

NAAS provides many benefits when compared to traditional uses of the `netmiko` library natively
in python scripts:

1. NAAS allows you to create a centralized location (or several) with access to network equipment.
 Users, or most commonly automation/orchestration tools, need only have access to NAAS to proxy their
 connections to the network devices. This is often useful in large networks where many different
 users/tools may need to talk to the network devices, but you wish to maintain a small number of
 allowed hosts on the network devices themselves for compliance/security reasons.
2. NAAS essentially proxies specific SSH/Telnet traffic via HTTPS, providing many benefits 
 (not least of which includes scalability).  Users or automation tools do not need to attempt SSH proxying, 
 which introduces considerable management overhead (for SSH config files and so forth) and complexity.
3. NAAS creates a RESTful interface for networking equipment that does not have one.  This is often
 useful if you're attempting to connect an orchestration tool to the network equipment, but that
 tool does not speak SSH.
4. NAAS is asynchronous, calls to `/send_command` or `/send_config` are stored in a job queue, and a
 job_id is returned to the requester.  They can simply call `/send_command/<job_id>` to see job status
 and retrieve any results/errors when it is complete.  This removes the need for blocking on simple command
 execution in automation and allows for greater scale as more workers can simply be added to reach more
 devices or work more quickly.
 
**Note**: While NAAS does provide an HTTP interface to network devices that may not have one today,
it does not (outside of basic TextFSM or Genie support in Netmiko) marshall/structure the returned data
from the network device in any way.  It is incumbent upon the consumer of the API to parse the
raw text response into useful data for their purposes.


## Running NAAS

There are several deployement scenarios for NAAS, depending on if you have an existing redis instance, etc.

### Full Deployment

The simplest, "batteries included", deployment launches the API and Worker containers, as well as a Redis instance:

1. Install Docker on a server that has access to your network devices
2. Join that host to (or initialize) a Docker Swarm
3. Clone the repo down from Github
4. Execute the following:
    * ```docker stack deploy --compose-file docker-compose.yml --compose-file docker-compose-redis.yml naas```
5. Validate that your service has deployed:
    * ```docker stack ps naas```
    * You should see 4 containers in the `Running` state:
        1. naas_api.1
        2. naas_worker.1
        3. naas_worker.2
        4. naas_redis.1
6. Perform an HTTP GET to `https://<your_server_ip>:5000/healthcheck` and look for a 200 response.

### Use Existing Redis

If you have an existing Redis instance you wish to use instead of a generic one launched by NAAS:

1. Install Docker on a server that has access to your network devices
2. Join that host to (or initialize) a Docker Swarm
3. Clone the repo down from Github
4. Ensure that the following environment variables are set in your launch environment:
    1. `REDIS_HOST`: A string of the IP/Hostname of the redis server you wish to use
    2. `REDIS_PORT`: An integer of the TCP Port number of the redis server you wish to use
    3. `REDIS_PASSWORD`: A string of the password for the redis server you wish to use (if authentication is needed)
5. Execute the following:
    * ```docker stack deploy --compose-file docker-compose.yml naas```
6. Validate that your service has deployed:
    * ```docker stack ps naas```
    * You should see 3 containers in the `Running` state:
        1. naas_api.1
        2. naas_worker.1
        3. naas_worker.2
7. Perform an HTTP GET to `https://<your_server_ip>:5000/healthcheck` and look for a 200 response.
