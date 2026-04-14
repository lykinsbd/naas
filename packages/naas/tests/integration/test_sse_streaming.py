"""Integration tests for SSE job streaming endpoint."""

import json
import uuid

import httpx
import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CISSHGO_HOST = "240.11.2.100"
CISSHGO_PORT = 10022
API_AUTH = ("admin", "admin")


@pytest.fixture(scope="session")
def api_url():
    return "https://localhost:18443"


def _parse_sse(text: str) -> list[dict]:
    """Parse SSE text into a list of event dicts."""
    events = []
    for block in text.strip().split("\n\n"):
        if not block:
            continue
        event: dict = {}
        for line in block.split("\n"):
            if line.startswith("event: "):
                event["event"] = line[7:]
            elif line.startswith("data: "):
                event["data"] = json.loads(line[6:])
        if event:
            events.append(event)
    return events


def _submit_job(api_url: str, **overrides) -> str:
    """Submit a send-command job and return the job_id."""
    payload = {
        "host": CISSHGO_HOST,
        "port": CISSHGO_PORT,
        "platform": "cisco_ios",
        "commands": ["show version"],
        "username": "admin",
        "password": "admin",
        **overrides,
    }
    r = requests.post(f"{api_url}/v2/send-command", json=payload, auth=API_AUTH, verify=False)
    assert r.status_code == 202, f"Expected 202, got {r.status_code}: {r.text}"
    return r.json()["job_id"]


class TestSseStreaming:
    """End-to-end SSE streaming tests against live stack."""

    def test_finished_job_streams_result(self, api_url):
        """Submit job, stream until result, verify output."""
        job_id = _submit_job(api_url)

        with httpx.Client(verify=False, timeout=30.0, auth=API_AUTH) as c:
            with c.stream("GET", f"{api_url}/v2/jobs/{job_id}/stream") as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers["content-type"]
                body = resp.read().decode()

        events = _parse_sse(body)
        assert len(events) >= 1

        terminal = events[-1]
        assert terminal["event"] == "result"
        assert terminal["data"]["status"] == "finished"
        assert terminal["data"]["job_id"] == job_id
        assert terminal["data"]["results"] is not None

    def test_failed_job_streams_error(self, api_url):
        """Job with unreachable host emits result event with error."""
        job_id = _submit_job(api_url, host="192.0.2.1", port=22)

        with httpx.Client(verify=False, timeout=30.0, auth=API_AUTH) as c:
            with c.stream("GET", f"{api_url}/v2/jobs/{job_id}/stream") as resp:
                body = resp.read().decode()

        events = _parse_sse(body)
        terminal = events[-1]
        assert terminal["event"] == "result"
        assert terminal["data"]["error"]
        assert terminal["data"]["results"] is None

    def test_not_found_returns_404(self, api_url):
        """Non-existent job returns 404."""
        fake_id = str(uuid.uuid4())
        r = requests.get(f"{api_url}/v2/jobs/{fake_id}/stream", auth=API_AUTH, verify=False)
        assert r.status_code == 404

    def test_event_sequence(self, api_url):
        """All events share the same job_id and end with a terminal event."""
        job_id = _submit_job(api_url, commands=["show version", "show ip interface brief"])

        with httpx.Client(verify=False, timeout=30.0, auth=API_AUTH) as c:
            with c.stream("GET", f"{api_url}/v2/jobs/{job_id}/stream") as resp:
                body = resp.read().decode()

        events = _parse_sse(body)
        assert len(events) >= 1

        for event in events:
            assert event["data"]["job_id"] == job_id

        assert events[-1]["event"] == "result"
        assert events[-1]["data"]["status"] in ("finished", "failed")
