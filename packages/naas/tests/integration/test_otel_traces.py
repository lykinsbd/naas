"""Integration tests for OpenTelemetry trace propagation.

Verifies the full trace chain: API → RQ queue → worker → netmiko,
using the OTLP collector's file exporter to read captured spans.
"""

import json
import subprocess
import time

import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CISSHGO_HOST = "240.11.2.100"
CISSHGO_PORT = 10022
API_AUTH = ("admin", "admin")
COMPOSE_FILE = "packages/naas/tests/integration/docker-compose.test.yml"


@pytest.fixture(scope="session")
def api_url():
    return "https://localhost:18443"


@pytest.fixture(scope="session")
def wait_for_api(api_url):
    """Wait for API to be ready and workers to be registered."""
    for _ in range(30):
        try:
            r = requests.get(f"{api_url}/healthcheck", verify=False, timeout=2)
            if r.status_code == 200:
                data = r.json()
                if data.get("components", {}).get("workers", {}).get("count", 0) > 0:
                    return
        except (requests.ConnectionError, ValueError):
            pass
        time.sleep(1)
    pytest.fail("API did not become ready with workers")


def _read_collector_spans() -> list[dict]:
    """Read spans from the otel-collector's file exporter via docker cp."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    result = subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "cp", "otel-collector:/traces/spans.json", tmp_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    try:
        content = open(tmp_path).read().strip()
    except FileNotFoundError:
        return []
    finally:
        import os

        os.unlink(tmp_path)
    if not content:
        return []
    spans = []
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            batch = json.loads(line)
            for rs in batch.get("resourceSpans", []):
                for ss in rs.get("scopeSpans", []):
                    spans.extend(ss.get("spans", []))
        except json.JSONDecodeError:
            continue
    return spans


def _submit_and_wait(api_url: str, timeout: int = 30) -> str:
    """Submit a send-command job and wait for completion. Returns job_id."""
    resp = requests.post(
        f"{api_url}/v2/send-command",
        json={
            "host": CISSHGO_HOST,
            "port": CISSHGO_PORT,
            "platform": "cisco_ios",
            "commands": ["show version"],
            "username": "admin",
            "password": "admin",
        },
        auth=API_AUTH,
        verify=False,
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    for _ in range(timeout):
        r = requests.get(f"{api_url}/v2/send-command/{job_id}", auth=API_AUTH, verify=False)
        if r.status_code == 200 and r.json().get("status") == "finished":
            return job_id
        time.sleep(1)
    pytest.fail(f"Job {job_id} did not complete within {timeout}s")


@pytest.mark.otel
class TestOtelTraces:
    def test_send_command_produces_linked_trace(self, api_url, wait_for_api) -> None:
        """Submit a job, wait for completion, verify full trace chain."""
        _submit_and_wait(api_url)

        # Give the collector a moment to flush
        time.sleep(3)

        spans = _read_collector_spans()
        assert len(spans) > 0, "No spans captured by collector"

        # Group spans by trace_id
        traces: dict[str, list[dict]] = {}
        for s in spans:
            tid = s["traceId"]
            traces.setdefault(tid, []).append(s)

        # Find a trace that has both API and worker spans
        matched_trace = None
        for _tid, trace_spans in traces.items():
            names = {s["name"] for s in trace_spans}
            if "naas.worker.execute" in names and any("naas.netmiko" in n for n in names):
                matched_trace = trace_spans
                break

        assert matched_trace is not None, (
            f"No trace found with worker + netmiko spans. Traces: {[{s['name'] for s in t} for t in traces.values()]}"
        )

        span_names = {s["name"] for s in matched_trace}
        assert "naas.worker.execute" in span_names
        assert any("naas.netmiko.connect" in n for n in span_names)
        assert any("naas.netmiko.send_command" in n for n in span_names)

        # Verify parent-child: netmiko spans should be children of worker span
        worker_span = next(s for s in matched_trace if s["name"] == "naas.worker.execute")
        netmiko_spans = [s for s in matched_trace if "naas.netmiko" in s["name"]]
        for ns in netmiko_spans:
            assert ns.get("parentSpanId") == worker_span["spanId"], (
                f"Span {ns['name']} parent {ns.get('parentSpanId')} != worker {worker_span['spanId']}"
            )
