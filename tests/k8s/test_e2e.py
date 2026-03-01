#!/usr/bin/env python3
"""
k8s end-to-end integration test.
Submits a send_command job targeting Cisshgo and asserts it completes successfully.

Usage:
    NAAS_URL=https://localhost:8443 python tests/k8s/test_e2e.py
"""

import os
import time
from typing import cast

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NAAS_URL = os.environ.get("NAAS_URL", "https://localhost:8443")
CISSHGO_HOST = os.environ.get("CISSHGO_HOST", "cisshgo")
CISSHGO_PORT = int(os.environ.get("CISSHGO_PORT", "10022"))
AUTH = ("admin", "admin")
TIMEOUT = 60


def wait_for_api(url: str, timeout: int = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{url}/healthcheck", verify=False, timeout=2)
            if r.status_code == 200:
                data = r.json()
                if data.get("components", {}).get("workers", {}).get("count", 0) > 0:
                    print(f"API ready: {data['status']}, workers: {data['components']['workers']['count']}")
                    return
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
    raise SystemExit(f"API at {url} did not become ready with workers in {timeout}s")


def submit_and_poll(url: str, payload: dict[str, object], timeout: int = TIMEOUT) -> dict[str, object]:
    r = requests.post(f"{url}/v1/send_command", json=payload, auth=AUTH, verify=False)
    if r.status_code != 202:
        raise SystemExit(f"Job submission failed: {r.status_code} {r.text}")

    job_id = cast(dict[str, str], r.json())["job_id"]
    print(f"Job submitted: {job_id}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        result = requests.get(f"{url}/v1/send_command/{job_id}", auth=AUTH, verify=False)
        data = cast(dict[str, object], result.json())
        if data["status"] in ("finished", "failed"):
            return data
        time.sleep(1)

    raise SystemExit(f"Job {job_id} did not complete within {timeout}s")


def main() -> None:
    print(f"NAAS URL: {NAAS_URL}")
    print(f"Cisshgo: {CISSHGO_HOST}:{CISSHGO_PORT}")

    wait_for_api(NAAS_URL, timeout=60)

    payload = {
        "ip": CISSHGO_HOST,
        "platform": "cisco_ios",
        "port": CISSHGO_PORT,
        "commands": ["show version"],
    }

    result = submit_and_poll(NAAS_URL, payload)
    status = cast(str, result["status"])
    print(f"Job result: status={status}")

    if status != "finished":
        raise SystemExit(f"FAIL: job status={status} error={result.get('error')}")

    results = cast(dict[str, str], result.get("results", {}))
    output = results.get("show version", "")
    if "Cisco IOS" not in output:
        raise SystemExit(f"FAIL: unexpected output: {output[:200]}")

    print("PASS: end-to-end job completed successfully")
    print(f"  show version output: {output[:80]}...")


if __name__ == "__main__":
    main()
