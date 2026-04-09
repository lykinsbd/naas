"""Tests for naas_client.models."""

from naas_client.models import (
    ApiKeyCreateResponse,
    ApiKeyListItem,
    ContextInfo,
    ContextsResponse,
    HealthCheckResponse,
    JobResult,
    JobStatus,
    JobSubmission,
)


class TestJobStatus:
    def test_values(self) -> None:
        assert JobStatus.QUEUED == "queued"
        assert JobStatus.STARTED == "started"
        assert JobStatus.FINISHED == "finished"
        assert JobStatus.FAILED == "failed"

    def test_from_string(self) -> None:
        assert JobStatus("finished") is JobStatus.FINISHED


class TestJobSubmission:
    def test_from_api_response(self) -> None:
        data = {
            "job_id": "abc-123",
            "message": "Job enqueued",
            "queue_position": 1,
            "enqueued_at": "2026-04-09T12:00:00Z",
            "timeout": 300,
        }
        job = JobSubmission.model_validate(data)
        assert job.job_id == "abc-123"
        assert job.queue_position == 1
        assert job.idempotent is False
        assert job.deduplicated is False

    def test_with_dedup_flags(self) -> None:
        data = {
            "job_id": "abc-123",
            "message": "Reusing existing job",
            "queue_position": 0,
            "enqueued_at": "2026-04-09T12:00:00Z",
            "timeout": 300,
            "idempotent": True,
            "deduplicated": True,
        }
        job = JobSubmission.model_validate(data)
        assert job.idempotent is True
        assert job.deduplicated is True


class TestJobResult:
    def test_finished_job(self) -> None:
        data = {
            "job_id": "abc-123",
            "status": "finished",
            "results": {"show version": "Cisco IOS ..."},
            "tags": {"env": "prod"},
        }
        result = JobResult.model_validate(data)
        assert result.status == "finished"
        assert result.results == {"show version": "Cisco IOS ..."}
        assert result.error is None

    def test_failed_job(self) -> None:
        data = {
            "job_id": "abc-123",
            "status": "failed",
            "error": "Connection refused",
        }
        result = JobResult.model_validate(data)
        assert result.status == "failed"
        assert result.error == "Connection refused"
        assert result.results is None

    def test_detected_platform(self) -> None:
        data = {
            "job_id": "abc-123",
            "status": "finished",
            "results": {},
            "detected_platform": "cisco_nxos",
        }
        result = JobResult.model_validate(data)
        assert result.detected_platform == "cisco_nxos"


class TestContextInfo:
    def test_from_api(self) -> None:
        ctx = ContextInfo.model_validate({"name": "default", "workers": 4, "queue_depth": 0})
        assert ctx.name == "default"
        assert ctx.workers == 4


class TestContextsResponse:
    def test_from_api(self) -> None:
        data = {"contexts": [{"name": "default", "workers": 4, "queue_depth": 0}]}
        resp = ContextsResponse.model_validate(data)
        assert len(resp.contexts) == 1


class TestApiKeyCreateResponse:
    def test_from_api(self) -> None:
        data = {
            "key_id": "k-abc123",
            "token": "eyJ...",
            "role": "operator",
            "contexts": ["default"],
            "expires_at": "2026-07-09T12:00:00Z",
        }
        info = ApiKeyCreateResponse.model_validate(data)
        assert info.key_id == "k-abc123"
        assert info.token == "eyJ..."


class TestApiKeyListItem:
    def test_from_api(self) -> None:
        data = {
            "key_id": "k-abc123",
            "role": "viewer",
            "contexts": ["default"],
            "created_at": "2026-04-09T12:00:00Z",
            "expires_at": "2026-07-09T12:00:00Z",
            "created_by": "admin",
        }
        info = ApiKeyListItem.model_validate(data)
        assert info.key_id == "k-abc123"
        assert info.created_by == "admin"


class TestHealthCheck:
    def test_from_api(self) -> None:
        data = {
            "status": "healthy",
            "version": "2.0.0",
            "uptime_seconds": 3600,
            "components": {
                "redis": {"status": "healthy"},
                "queue": {"status": "healthy", "depth": 0},
                "workers": {"status": "healthy", "count": 4, "active_jobs": 0},
                "failed_jobs": 0,
            },
        }
        health = HealthCheckResponse.model_validate(data)
        assert health.status == "healthy"
        assert health.version == "2.0.0"
        assert health.components.redis.status == "healthy"
        assert health.components.workers.count == 4
