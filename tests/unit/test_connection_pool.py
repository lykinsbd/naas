"""Unit tests for connection_pool module."""

from unittest.mock import MagicMock, patch

import pytest

from naas.library.connection_pool import ConnectionPool


@pytest.fixture
def pool():
    return ConnectionPool()


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    conn.is_alive.return_value = True
    return conn


class TestConnectionPoolGet:
    """Tests for ConnectionPool.get()."""

    def test_get_miss_returns_none(self, pool):
        """Returns None when no pooled connection exists."""
        assert pool.get("1.2.3.4", 22, "user", "cisco_ios") is None

    def test_get_hit_returns_connection(self, pool, mock_conn):
        """Returns pooled connection on cache hit."""
        pool.release("1.2.3.4", 22, "user", "cisco_ios", mock_conn)
        result = pool.get("1.2.3.4", 22, "user", "cisco_ios")
        assert result is mock_conn

    def test_get_evicts_dead_connection(self, pool, mock_conn):
        """Evicts and returns None when is_alive() is False."""
        mock_conn.is_alive.return_value = False
        pool.release("1.2.3.4", 22, "user", "cisco_ios", mock_conn)
        result = pool.get("1.2.3.4", 22, "user", "cisco_ios")
        assert result is None
        mock_conn.disconnect.assert_called_once()

    def test_get_evicts_idle_connection(self, pool, mock_conn):
        """Evicts and returns None when idle timeout exceeded."""
        pool.release("1.2.3.4", 22, "user", "cisco_ios", mock_conn)
        with patch("naas.library.connection_pool.CONNECTION_POOL_IDLE_TIMEOUT", 0):
            result = pool.get("1.2.3.4", 22, "user", "cisco_ios")
        assert result is None
        mock_conn.disconnect.assert_called_once()

    def test_get_evicts_aged_connection(self, pool, mock_conn):
        """Evicts and returns None when max age exceeded."""
        pool.release("1.2.3.4", 22, "user", "cisco_ios", mock_conn)
        with patch("naas.library.connection_pool.CONNECTION_POOL_MAX_AGE", 0):
            result = pool.get("1.2.3.4", 22, "user", "cisco_ios")
        assert result is None
        mock_conn.disconnect.assert_called_once()

    def test_get_key_includes_credentials(self, pool, mock_conn):
        """Different usernames produce different pool keys."""
        pool.release("1.2.3.4", 22, "user1", "cisco_ios", mock_conn)
        assert pool.get("1.2.3.4", 22, "user2", "cisco_ios") is None


class TestConnectionPoolRelease:
    """Tests for ConnectionPool.release()."""

    def test_release_stores_connection(self, pool, mock_conn):
        """Connection is stored and retrievable after release."""
        pool.release("1.2.3.4", 22, "user", "cisco_ios", mock_conn)
        assert pool.get("1.2.3.4", 22, "user", "cisco_ios") is mock_conn

    def test_release_at_capacity_disconnects(self, pool):
        """Discards and disconnects connection when pool is at capacity."""
        with patch("naas.library.connection_pool.CONNECTION_POOL_MAX_SIZE", 1):
            conn1 = MagicMock()
            conn1.is_alive.return_value = True
            conn2 = MagicMock()
            pool.release("1.2.3.4", 22, "user", "cisco_ios", conn1)
            pool.release("1.2.3.5", 22, "user", "cisco_ios", conn2)
            conn2.disconnect.assert_called_once()

    def test_release_at_capacity_handles_disconnect_error(self, pool):
        """Handles disconnect error gracefully when discarding at capacity."""
        with patch("naas.library.connection_pool.CONNECTION_POOL_MAX_SIZE", 1):
            conn1 = MagicMock()
            conn1.is_alive.return_value = True
            conn2 = MagicMock()
            conn2.disconnect.side_effect = Exception("disconnect failed")
            pool.release("1.2.3.4", 22, "user", "cisco_ios", conn1)
            pool.release("1.2.3.5", 22, "user", "cisco_ios", conn2)  # Should not raise

    def test_release_updates_existing_entry(self, pool, mock_conn):
        """Re-releasing same key updates last_used timestamp."""
        pool.release("1.2.3.4", 22, "user", "cisco_ios", mock_conn)
        pool.release("1.2.3.4", 22, "user", "cisco_ios", mock_conn)
        assert len(pool._pool) == 1


class TestConnectionPoolDrain:
    """Tests for ConnectionPool.drain()."""

    def test_drain_disconnects_all(self, pool):
        """drain() disconnects all pooled connections."""
        conns = [MagicMock() for _ in range(3)]
        for i, conn in enumerate(conns):
            conn.is_alive.return_value = True
            pool.release(f"1.2.3.{i}", 22, "user", "cisco_ios", conn)

        pool.drain()

        assert len(pool._pool) == 0
        for conn in conns:
            conn.disconnect.assert_called_once()

    def test_drain_handles_disconnect_error(self, pool, mock_conn):
        """drain() continues even if disconnect raises."""
        mock_conn.disconnect.side_effect = Exception("disconnect failed")
        pool.release("1.2.3.4", 22, "user", "cisco_ios", mock_conn)
        pool.drain()  # Should not raise
        assert len(pool._pool) == 0
