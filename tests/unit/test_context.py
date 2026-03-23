"""Unit tests for context routing."""

from unittest.mock import MagicMock, patch

import pytest

from naas.library.context import get_queue_for_context
from naas.library.errorhandlers import InvalidContext, NoWorkersForContext


class TestGetQueueForContext:
    def test_invalid_context_raises(self, fake_redis):
        """Unknown context raises InvalidContext."""
        with patch("naas.library.context.NAAS_CONTEXTS", frozenset({"default"})):
            with pytest.raises(InvalidContext):
                get_queue_for_context("unknown-context", fake_redis)

    def test_no_workers_raises(self, fake_redis):
        """Valid context with no active workers raises NoWorkersForContext."""
        with patch("naas.library.context.NAAS_CONTEXTS", frozenset({"default"})):
            with patch("naas.library.context.Worker.all", return_value=[]):
                with pytest.raises(NoWorkersForContext):
                    get_queue_for_context("default", fake_redis)

    def test_returns_queue_when_worker_available(self, fake_redis):
        """Valid context with active worker returns Queue."""
        mock_worker = MagicMock()
        mock_worker.queue_names.return_value = ["naas-default"]
        with patch("naas.library.context.NAAS_CONTEXTS", frozenset({"default"})):
            with patch("naas.library.context.Worker.all", return_value=[mock_worker]):
                with patch("naas.library.context.Queue") as mock_queue_cls:
                    result = get_queue_for_context("default", fake_redis)
                    mock_queue_cls.assert_called_once_with("naas-default", connection=fake_redis)
                    assert result == mock_queue_cls.return_value
