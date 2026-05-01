"""NAAS load test scenarios using Locust.

Profiles:
  smoke: 30s, 10 users — quick regression check (CI on every PR)
  full:  10min, ramp to 100 users — capacity baseline (CI on RC tags)

Usage:
  # Smoke (headless)
  locust -f tests/load/locustfile.py --headless -u 10 -r 10 -t 30s --host https://localhost:18443

  # Full profile (headless)
  locust -f tests/load/locustfile.py --headless -u 100 -r 10 -t 10m --host https://localhost:18443

  # Web UI
  locust -f tests/load/locustfile.py --host https://localhost:18443
"""

from __future__ import annotations

import os
import time

from locust import HttpUser, between, events, task


class NaasUser(HttpUser):
    """Simulates a NAAS API consumer submitting jobs and reading state."""

    wait_time = between(0.5, 2)
    insecure = True  # skip TLS verification for self-signed certs

    def on_start(self) -> None:
        """Authenticate and store headers."""
        self.api_key = os.environ.get("NAAS_LOAD_API_KEY", "")
        username = os.environ.get("NAAS_LOAD_USERNAME", "admin")
        password = os.environ.get("NAAS_LOAD_PASSWORD", "admin")

        if self.api_key:
            self.headers = {"Authorization": f"Bearer {self.api_key}"}
        else:
            self.headers = {}
            self.client.auth = (username, password)

        self.client.verify = False
        self.device_host = os.environ.get("NAAS_LOAD_DEVICE", "cisshgo")
        self.device_port = int(os.environ.get("NAAS_LOAD_DEVICE_PORT", "10022"))

    @task(3)
    def send_command_and_wait(self) -> None:
        """Submit a show command job and poll until complete."""
        payload = {
            "host": self.device_host,
            "platform": "cisco_ios",
            "commands": ["show version"],
            "port": self.device_port,
        }

        with self.client.post(
            "/v2/send-command",
            json=payload,
            headers=self.headers,
            name="/v2/send-command [submit]",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 201, 202):
                resp.failure(f"Submit failed: {resp.status_code}")
                return
            job_id = resp.json().get("job_id")
            if not job_id:
                resp.failure("No job_id in response")
                return

        # Poll until terminal state
        start = time.monotonic()
        while True:
            with self.client.get(
                f"/v2/send-command/{job_id}",
                headers=self.headers,
                name="/v2/send-command/{id} [poll]",
                catch_response=True,
            ) as poll_resp:
                if poll_resp.status_code != 200:
                    poll_resp.failure(f"Poll failed: {poll_resp.status_code}")
                    return
                data = poll_resp.json()
                status = data.get("status")
                if status in ("finished", "failed"):
                    elapsed_ms = (time.monotonic() - start) * 1000
                    events.request.fire(
                        request_type="JOB",
                        name="send_command [e2e]",
                        response_time=elapsed_ms,
                        response_length=len(poll_resp.text),
                        exception=None if status == "finished" else Exception(f"Job failed: {data.get('error')}"),
                        context={},
                    )
                    if status == "failed":
                        poll_resp.failure(f"Job failed: {data.get('error')}")
                    return

            if time.monotonic() - start > 60:
                events.request.fire(
                    request_type="JOB",
                    name="send_command [e2e]",
                    response_time=(time.monotonic() - start) * 1000,
                    response_length=0,
                    exception=Exception("Job poll timeout"),
                    context={},
                )
                return

            time.sleep(1)

    @task(1)
    def list_jobs(self) -> None:
        """List jobs — measures API responsiveness under load."""
        self.client.get("/v2/jobs", headers=self.headers, name="/v2/jobs")

    @task(1)
    def healthcheck(self) -> None:
        """Healthcheck — lightweight read to measure baseline latency."""
        self.client.get("/healthcheck", headers=self.headers, name="/healthcheck")
