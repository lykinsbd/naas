#!/usr/bin/env python3
"""
k8s end-to-end integration test.
Submits a send_command job targeting Cisshgo via NaasClient and asserts it completes.

Usage:
    NAAS_URL=https://localhost:8443 CISSHGO_HOST=10.0.0.1 python tests/k8s/test_e2e.py
"""

import os
import time

from naas_client import NaasClient
from naas_client.models import JobStatus

NAAS_URL = os.environ.get("NAAS_URL", "https://localhost:8443")
CISSHGO_HOST = os.environ.get("CISSHGO_HOST", "cisshgo")
CISSHGO_PORT = int(os.environ.get("CISSHGO_PORT", "10022"))
TIMEOUT = 60


def wait_for_api(url: str, timeout: int = 30) -> None:
    """Wait for NAAS API to be ready with workers."""
    deadline = time.time() + timeout
    client = NaasClient(url, username="admin", password="admin", verify=False, timeout=2.0)
    while time.time() < deadline:
        try:
            health = client.healthcheck()
            count = health.components.workers.count or 0
            if count > 0:
                print(f"API ready: status={health.status}, workers={count}")
                client.close()
                return
        except Exception:
            pass
        time.sleep(2)
    client.close()
    raise SystemExit(f"API at {url} did not become ready with workers in {timeout}s")


def main() -> None:
    print(f"NAAS URL: {NAAS_URL}")
    print(f"Cisshgo: {CISSHGO_HOST}:{CISSHGO_PORT}")

    wait_for_api(NAAS_URL, timeout=60)

    with NaasClient(NAAS_URL, username="admin", password="admin", verify=False) as client:
        job = client.send_command(
            host=CISSHGO_HOST,
            platform="cisco_ios",
            port=CISSHGO_PORT,
            commands=["show version"],
        )
        print(f"Job submitted: {job.job_id}")

        result = job.wait(timeout=TIMEOUT)
        print(f"Job result: status={result.status}")

        if result.status != JobStatus.FINISHED:
            raise SystemExit(f"FAIL: job status={result.status} error={result.error}")

        output = (result.results or {}).get("show version", "")
        if "Cisco IOS" not in output:
            raise SystemExit(f"FAIL: unexpected output: {output[:200]}")

        print("PASS: end-to-end job completed successfully")
        print(f"  show version output: {output[:80]}...")


if __name__ == "__main__":
    main()
