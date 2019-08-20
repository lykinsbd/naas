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

### Standard Deployment

The Standard Deployment of NAAS is the simplest, "batteries included", deployment.  It launches the API and Worker containers, as well as a Redis instance:

1. [Install Docker](https://docs.docker.com/install/) on a server or VM that has management/SSH access to your network devices
2. Join that host to (or initialize) a [Docker Swarm](https://docs.docker.com/engine/swarm/swarm-tutorial/)
3. Clone the repo down from Github
    * `git clone https://github.com/lykinsbd/naas.git`
4. If you wish to use a custom Redis password (recommended) set it via an environment variable:
    * `REDIS_PASSWORD`: A string of the password you wish to use for the redis server
5. Execute the following:
    * ```docker stack deploy --compose-file docker-compose.yml --compose-file docker-compose-redis.yml naas```
6. Validate that your service has deployed:
    * ```docker stack ps naas```
    * You should see 4 containers in the `Running` state:
        1. naas_api.1
        2. naas_worker.1
        3. naas_worker.2
        4. naas_redis.1
7. Perform an HTTP GET to `https://<your_server_ip>:8443/healthcheck` and look for a 200 response.

### Custom Deployment

NAAS can be customized to fit most environments through a combination of stacked Docker Compose files
 and environment variables.  You may wish to utilize the Custom Deployment model if for example:

* You have an existing Redis instance you wish to use instead of a generic one launched by NAAS
* You wish to expose the API on a different TCP port than the default (8443)

To launch a more customized deployment, please follow these steps:

1. [Install Docker](https://docs.docker.com/install/) on a server or VM that has management/SSH access to your network devices
2. Join that host to (or initialize) a [Docker Swarm](https://docs.docker.com/engine/swarm/swarm-tutorial/)
3. Clone the repo down from Github
    * `git clone https://github.com/lykinsbd/naas.git`
4. You have the following options available for customization:
    1. To use a custom Redis instance, ensure that the following environment variables are set in your launch environment:
        1. `REDIS_HOST`: A string of the IP/Hostname of the redis server you wish to use (Default: redis)
        2. `REDIS_PORT`: An integer of the TCP Port number of the redis server you wish to use (Default: 6379)
        3. `REDIS_PASSWORD`: A string of the password for the redis server you wish to use (if authentication is needed)
    2. To use a custom global/published TCP port for the API front end, 
        set the following environment variable in your launch environment:
        1. `NAAS_GLOBAL_PORT`: An integer of the TCP port you want to expose NAAS on to the outside world (Default: 8443)
    3. To customize the number of NAAS worker containers or worker processes in a container, 
        set the following environment variables in your launch environment:
        1. `NAAS_WORKER_REPLICAS`: An integer of the number of Worker container replicas you want (Default: 2)
        2. `NAAS_WORKER_PROCESSES`: An integer of the number of Worker processes you want in each Worker container (Default: 100)
5. Execute the following to launch NAAS:
    1. With a custom Redis server as defined in step 4:
        * ```docker stack deploy --compose-file docker-compose.yml naas```
    2. With the default Redis container:
        * ```docker stack deploy --compose-file docker-compose.yml --compose-file docker-compose-redis.yml naas```
6. Validate that your service has deployed:
    * ```docker stack ps naas```
    * You should see 3 containers in the `Running` state if you used a custom Redis server
        (otherwise you'll see 4 as shown in the Standard Deployment):
        1. naas_api.1
        2. naas_worker.1
        3. naas_worker.2
7. Perform an HTTP GET to `https://<your_server_ip>:<NAAS_GLOBAL_PORT>/healthcheck` and look for a 200 response.
