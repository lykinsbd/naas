#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
worker.py
Author: Brett Lykins (lykinsbd@gmail.com)
Description: Handle launching of rq workers
"""

import os
import signal
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from logging import basicConfig, getLogger
from multiprocessing import Process
from pathlib import Path
from socket import gethostname
from time import sleep

from redis import Redis
from rq import Queue, Worker

from naas.config import WORKER_CONTEXTS
from naas.library.netmiko_lib import netmiko_send_command, netmiko_send_config  # noqa F401

logger = getLogger("naas_worker")


def main() -> None:
    """
    Launch rq workers, default of 50
    :return:
    """

    # Parse some args
    args = arg_parsing()

    # Setup logging
    basicConfig(
        level=args.log_level,
        format="[%(asctime)s] [%(process)d] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S %z",
    )

    # Initialize worker metrics (must happen before forking children)
    # Initialize OpenTelemetry (no-op when OTEL_ENABLED=false)
    from naas.library.otel import init_telemetry
    from naas.library.worker_metrics import init, make_registry

    init_telemetry(service_name="naas-worker")

    metrics_dir = init()
    logger.debug("Worker metrics directory: %s", metrics_dir)

    metrics_port = int(os.environ.get("WORKER_METRICS_PORT", "9090"))
    from prometheus_client import start_http_server

    start_http_server(metrics_port, registry=make_registry())
    logger.info("Worker metrics server started on port %s", metrics_port)

    # Sleep 10 seconds to allow Redis to come up
    logger.debug("Sleeping %s seconds to allow Redis to initialize.", args.sleep)
    sleep(args.sleep)

    # Launch the workers
    logger.debug("Creating %s workers", args.workers)
    processes = []
    hostname = gethostname()
    for w in range(1, args.workers + 1):
        proc = Process(
            target=worker_launch,
            kwargs={
                "name": f"naas_{hostname}_{w}",
                "queues": args.queues,
                "redis_host": args.redis,
                "redis_port": args.port,
                "redis_pw": args.auth_password,
                "log_level": args.log_level,
            },
        )
        processes.append(proc)
        proc.start()

    # Main loop: write heartbeat file and monitor child processes
    heartbeat_file = Path(os.environ.get("WORKER_HEARTBEAT_FILE", "/tmp/worker_heartbeat"))
    _running = True

    def _stop(signum, frame):
        nonlocal _running
        _running = False

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    while _running and any(p.is_alive() for p in processes):
        heartbeat_file.touch()
        sleep(30)

    heartbeat_file.unlink(missing_ok=True)


def arg_parsing() -> Namespace:
    """
    Parse the CLI arguments and return them in an Argparse Namespace
    :return:
    """

    argparser = ArgumentParser(description="RQ Multi-worker Launcher")
    argparser.add_argument(
        "workers", type=int, nargs="?", default=100, help="The number of workers to launch. Default: 100"
    )
    argparser.add_argument(
        "-q",
        "--queues",
        type=str,
        nargs="+",
        default=[f"naas-{c}" for c in WORKER_CONTEXTS],
        help=f"Queue(s) to work from. Default: derived from WORKER_CONTEXTS env var ({WORKER_CONTEXTS})",
    )
    argparser.add_argument(
        "-r", "--redis", type=str, default="redis", help="What Redis server are we using? Defualt: redis"
    )
    argparser.add_argument(
        "-p", "--port", type=int, default=6379, help="What port is the Redis server listening on? Default: 6379"
    )
    argparser.add_argument(
        "-a", "--auth_password", type=str, help="Password if the Redis server requires authentication."
    )
    argparser.add_argument(
        "-s",
        "--sleep",
        type=int,
        default=10,
        nargs="?",
        help="How many seconds to sleep to give Redis a chance to initialize. Default: 10",
    )
    argparser.add_argument(
        "-l",
        "--log_level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="What log-level are we to log at",
    )

    return argparser.parse_args()


def worker_launch(
    name: str, queues: Sequence[Queue], redis_host: str, redis_port: int, log_level: str, redis_pw: str | None = None
) -> None:
    """
    Function for launching an rq worker
    :param name:
    :param queues:
    :param redis_host:
    :param redis_port:
    :param redis_pw:
    :param log_level:
    :return:
    """

    # Initialize our Redis connection
    logger.debug("Initializing Redis connection to redis://%s:%s", redis_host, str(redis_port))
    if redis_pw:
        redis_conn = Redis(host=redis_host, port=redis_port, password=redis_pw)
    else:
        redis_conn = Redis(host=redis_host, port=redis_port)

    logger.debug(
        "Starting rq worker %s, with connection to redis://%s:%s, to watch the following queue(s): %s",
        name,
        redis_host,
        redis_port,
        queues,
    )
    w = Worker(queues=queues, name=name, connection=redis_conn)

    # Increment active_jobs gauge and create OTel span when a job starts executing
    from naas.library.otel import extract_context, span
    from naas.library.worker_metrics import active_jobs

    original_perform = w.perform_job

    def _perform_with_metrics(job, queue):
        active_jobs.inc()
        meta = job.meta if isinstance(job.meta, dict) else {}
        parent_ctx = extract_context(meta)
        with span(
            "naas.worker.execute",
            attributes={"job.id": job.id, "job.func": job.func_name, "context": meta.get("context", "default")},
            parent_context=parent_ctx,
        ):
            return original_perform(job, queue)

    w.perform_job = _perform_with_metrics

    # Fetch credential salt from Redis and configure the connection pool
    from naas.library.connection_pool import pool

    salt = redis_conn.get("naas_cred_salt")
    if salt:
        pool.set_salt(salt.decode())
    else:
        logger.warning("naas_cred_salt not found in Redis — connection pooling will be disabled until salt is set")

    # Start job reaper background thread
    from naas.library.reaper import start_reaper

    start_reaper(redis_conn)

    # Setup signal handlers for graceful shutdown
    def request_stop(signum, frame):
        logger.info("Received signal %s, requesting graceful shutdown", signum)
        w.request_stop(signum, frame)
        from naas.library.connection_pool import pool

        pool.drain()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    w.work(logging_level=log_level, max_jobs=None, with_scheduler=False)


if __name__ == "__main__":
    main()
