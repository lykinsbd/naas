#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
test_worker.py
Tests for worker graceful shutdown functionality
"""

import os
from importlib import reload


def test_shutdown_timeout_config_default():
    """Test that SHUTDOWN_TIMEOUT defaults to 30 seconds"""
    if "SHUTDOWN_TIMEOUT" in os.environ:
        del os.environ["SHUTDOWN_TIMEOUT"]

    import naas.config

    reload(naas.config)
    assert naas.config.SHUTDOWN_TIMEOUT == 30


def test_shutdown_timeout_config_custom():
    """Test that SHUTDOWN_TIMEOUT is configurable via env var"""
    os.environ["SHUTDOWN_TIMEOUT"] = "60"

    import naas.config

    reload(naas.config)
    assert naas.config.SHUTDOWN_TIMEOUT == 60

    # Cleanup
    del os.environ["SHUTDOWN_TIMEOUT"]
    reload(naas.config)


def test_worker_has_signal_handlers():
    """Test that worker module sets up signal handlers"""
    import signal
    from unittest.mock import MagicMock, patch

    from worker import worker_launch

    # Mock Worker to prevent actual work loop
    with patch("worker.Worker") as mock_worker_class, patch("worker.Redis"):
        mock_worker = MagicMock()
        mock_worker.work = MagicMock(side_effect=KeyboardInterrupt)  # Exit immediately
        mock_worker_class.return_value = mock_worker

        # Track signal registrations
        original_signal = signal.signal
        signal_calls = []

        def track_signal(sig, handler):
            signal_calls.append((sig, handler))
            return original_signal(sig, handler)

        with patch("worker.signal.signal", side_effect=track_signal):
            try:
                worker_launch(
                    name="test",
                    queues=["test"],
                    redis_host="localhost",
                    redis_port=6379,
                    log_level="INFO",
                )
            except KeyboardInterrupt:
                pass

        # Verify SIGTERM and SIGINT handlers were registered
        registered_signals = [sig for sig, _ in signal_calls]
        assert signal.SIGTERM in registered_signals
        assert signal.SIGINT in registered_signals
