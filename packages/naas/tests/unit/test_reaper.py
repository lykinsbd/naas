"""Unit tests for the job reaper."""

import threading
import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from naas.library.reaper import _is_worker_stale, reap_orphaned_jobs, start_reaper


class TestIsWorkerStale:
    def test_stale_when_no_heartbeat(self):
        """Worker with no heartbeat is considered stale."""
        worker = MagicMock()
        worker.last_heartbeat = None
        assert _is_worker_stale(worker, 120) is True

    def test_stale_when_heartbeat_old(self):
        """Worker with old heartbeat is stale."""
        worker = MagicMock()
        worker.last_heartbeat = datetime.fromtimestamp(time.time() - 200, tz=UTC)
        assert _is_worker_stale(worker, 120) is True

    def test_not_stale_when_heartbeat_recent(self):
        """Worker with recent heartbeat is not stale."""
        worker = MagicMock()
        worker.last_heartbeat = datetime.fromtimestamp(time.time() - 10, tz=UTC)
        assert _is_worker_stale(worker, 120) is False


class TestReapOrphanedJobs:
    def test_skips_when_lock_not_acquired(self, fake_redis):
        """Returns 0 when another reaper holds the lock."""
        fake_redis.set("naas:reaper:lock", "other-reaper", ex=60)
        result = reap_orphaned_jobs(fake_redis)
        assert result == 0

    def test_reaps_job_with_dead_worker(self, fake_redis):
        """Moves orphaned job to FailedJobRegistry when worker is gone."""
        mock_job = MagicMock()
        mock_job.id = "orphaned-job"
        mock_job.worker_name = "dead-worker"
        mock_job.meta = {}

        with patch("naas.library.reaper.StartedJobRegistry") as mock_started:
            with patch("naas.library.reaper.FailedJobRegistry") as mock_failed:
                with patch("naas.library.reaper.Worker.all", return_value=[]):
                    with patch("naas.library.reaper.Job.fetch", return_value=mock_job):
                        with patch("naas.library.audit.emit_audit_event"):
                            mock_started.return_value.get_job_ids.return_value = ["orphaned-job"]
                            result = reap_orphaned_jobs(fake_redis)

        assert result == 1
        mock_failed.return_value.add.assert_called_once()
        mock_job.set_status.assert_called_once()

    def test_skips_healthy_job(self, fake_redis):
        """Does not reap jobs whose worker is alive and healthy."""
        mock_worker = MagicMock()
        mock_worker.name = "healthy-worker"
        mock_worker.last_heartbeat = datetime.fromtimestamp(time.time() - 5, tz=UTC)

        mock_job = MagicMock()
        mock_job.id = "healthy-job"
        mock_job.worker_name = "healthy-worker"
        mock_job.meta = {}

        with patch("naas.library.reaper.StartedJobRegistry") as mock_started:
            with patch("naas.library.reaper.FailedJobRegistry") as mock_failed:
                with patch("naas.library.reaper.Worker.all", return_value=[mock_worker]):
                    with patch("naas.library.reaper.Job.fetch", return_value=mock_job):
                        mock_started.return_value.get_job_ids.return_value = ["healthy-job"]
                        result = reap_orphaned_jobs(fake_redis)

        assert result == 0
        mock_failed.return_value.add.assert_not_called()

    def test_clears_dedup_key_on_reap(self, fake_redis):
        """Clears dedup key when reaping an orphaned job."""
        fake_redis.set("naas:dedup:abc123", "orphaned-job")

        mock_job = MagicMock()
        mock_job.id = "orphaned-job"
        mock_job.worker_name = "dead-worker"
        mock_job.meta = {"dedup_key": "naas:dedup:abc123"}

        with patch("naas.library.reaper.StartedJobRegistry") as mock_started:
            with patch("naas.library.reaper.FailedJobRegistry"):
                with patch("naas.library.reaper.Worker.all", return_value=[]):
                    with patch("naas.library.reaper.Job.fetch", return_value=mock_job):
                        with patch("naas.library.audit.emit_audit_event"):
                            mock_started.return_value.get_job_ids.return_value = ["orphaned-job"]
                            reap_orphaned_jobs(fake_redis)

        assert fake_redis.get("naas:dedup:abc123") is None

    def test_skips_unfetchable_job(self, fake_redis):
        """Skips jobs that can't be fetched (e.g. already expired)."""
        with patch("naas.library.reaper.StartedJobRegistry") as mock_started:
            with patch("naas.library.reaper.FailedJobRegistry") as mock_failed:
                with patch("naas.library.reaper.Worker.all", return_value=[]):
                    with patch("naas.library.reaper.Job.fetch", side_effect=Exception("gone")):
                        mock_started.return_value.get_job_ids.return_value = ["gone-job"]
                        result = reap_orphaned_jobs(fake_redis)

        assert result == 0
        mock_failed.return_value.add.assert_not_called()
        """Lock is released after reaper completes."""
        with patch("naas.library.reaper.StartedJobRegistry") as mock_started:
            with patch("naas.library.reaper.Worker.all", return_value=[]):
                mock_started.return_value.get_job_ids.return_value = []
                reap_orphaned_jobs(fake_redis)

        assert fake_redis.get("naas:reaper:lock") is None


class TestStartReaper:
    def test_returns_thread_when_enabled(self, fake_redis):
        """start_reaper returns a running daemon thread."""
        with patch("naas.library.reaper.JOB_REAPER_ENABLED", True):
            with patch("naas.library.reaper.JOB_REAPER_INTERVAL", 9999):  # prevent actual sleep
                thread = start_reaper(fake_redis)
        assert isinstance(thread, threading.Thread)
        assert thread.daemon is True

    def test_reaper_loop_calls_reap(self, fake_redis):
        """Reaper thread calls reap_orphaned_jobs and handles errors gracefully."""
        call_count = []

        def mock_reap(redis):
            call_count.append(1)
            if len(call_count) == 1:
                raise RuntimeError("transient error")  # Test error handling
            raise SystemExit  # Stop the loop after second call

        with patch("naas.library.reaper.JOB_REAPER_ENABLED", True):
            with patch("naas.library.reaper.JOB_REAPER_INTERVAL", 0):
                with patch("naas.library.reaper.reap_orphaned_jobs", side_effect=mock_reap):
                    thread = start_reaper(fake_redis)
                    thread.join(timeout=2)

        assert len(call_count) >= 1

    def test_returns_noop_when_disabled(self, fake_redis):
        """start_reaper returns a no-op thread when disabled."""
        with patch("naas.library.reaper.JOB_REAPER_ENABLED", False):
            thread = start_reaper(fake_redis)
        assert isinstance(thread, threading.Thread)
        assert not thread.is_alive()
