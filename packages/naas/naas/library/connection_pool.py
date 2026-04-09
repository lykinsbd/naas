"""
connection_pool.py
Per-process SSH connection pool for reusing Netmiko connections across jobs.
Reduces VTY session overhead on network devices.
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from naas.config import (
    CONNECTION_POOL_EXCLUDE,
    CONNECTION_POOL_IDLE_TIMEOUT,
    CONNECTION_POOL_MAX_AGE,
    CONNECTION_POOL_MAX_SIZE,
)

if TYPE_CHECKING:
    import netmiko

logger = logging.getLogger(name="NAAS")


@dataclass
class _PoolEntry:
    connection: "netmiko.BaseConnection"
    created_at: float = field(default_factory=time.monotonic)
    last_used: float = field(default_factory=time.monotonic)


class ConnectionPool:
    """
    Per-process pool of reusable Netmiko SSH connections.

    Pool key: (ip, port, sha512(username:password+salt), platform) — credentials
    must match exactly. The salt is fetched from Redis at worker startup via
    set_salt() and matches the salt used by Credentials.salted_hash() in the API.

    RQ workers are single-threaded so no locking is required within a process.
    """

    def __init__(self) -> None:
        self._pool: dict[tuple, _PoolEntry] = {}
        self._salt: str | None = None

    def set_salt(self, salt: str) -> None:
        """
        Set the credential salt used for pool key hashing.
        Must be called at worker startup before any jobs run.

        Args:
            salt: The naas_cred_salt value from Redis.
        """
        self._salt = salt

    def _cred_hash(self, username: str, password: str) -> str | None:
        """Return SHA512 hash of username:password+salt, or None if salt not set."""
        if self._salt is None:
            return None
        return hashlib.sha512(f"{username}:{password}{self._salt}".encode()).hexdigest()

    def get(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        platform: str,
    ) -> "netmiko.BaseConnection | None":
        """
        Return a live pooled connection for the given key, or None if unavailable.
        Evicts stale/dead entries on access. Returns None if salt not yet set.

        Args:
            ip: Device IP address
            port: SSH port
            username: Device username
            password: Device password
            platform: Netmiko device_type

        Returns:
            A live BaseConnection, or None if no valid pooled connection exists.
        """
        cred_hash = self._cred_hash(username, password)
        if cred_hash is None:
            logger.debug("Pool skipping: salt not set")
            return None

        if ip in CONNECTION_POOL_EXCLUDE or platform in CONNECTION_POOL_EXCLUDE:
            logger.debug("Pool skipping: %s (%s) is in exclusion list", ip, platform)
            return None

        key = (ip, port, cred_hash, platform)
        entry = self._pool.get(key)
        if entry is None:
            return None

        now = time.monotonic()
        age = now - entry.created_at
        idle = now - entry.last_used

        if age > CONNECTION_POOL_MAX_AGE or idle > CONNECTION_POOL_IDLE_TIMEOUT:
            logger.debug("Pool evicting %s:%s (age=%.0fs idle=%.0fs)", ip, port, age, idle)
            self._evict(key)
            return None

        if not entry.connection.is_alive():
            logger.debug("Pool evicting dead connection to %s:%s", ip, port)
            self._evict(key)
            return None

        logger.debug("Pool hit for %s:%s", ip, port)
        entry.last_used = now
        return entry.connection

    def release(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        platform: str,
        connection: "netmiko.BaseConnection",
    ) -> None:
        """
        Return a connection to the pool after successful use.
        Discards if pool is at capacity or salt not set.

        Args:
            ip: Device IP address
            port: SSH port
            username: Device username
            password: Device password
            platform: Netmiko device_type
            connection: The connection to return
        """
        cred_hash = self._cred_hash(username, password)
        if cred_hash is None:
            logger.debug("Pool skipping release: salt not set")
            try:
                connection.disconnect()
            except Exception:
                pass
            return

        if len(self._pool) >= CONNECTION_POOL_MAX_SIZE:
            logger.debug("Pool at capacity (%d), discarding connection to %s:%s", CONNECTION_POOL_MAX_SIZE, ip, port)
            try:
                connection.disconnect()
            except Exception:
                pass
            return

        key = (ip, port, cred_hash, platform)
        entry = self._pool.get(key)
        if entry is not None:
            entry.last_used = time.monotonic()
        else:
            self._pool[key] = _PoolEntry(
                connection=connection,
                created_at=time.monotonic(),
                last_used=time.monotonic(),
            )
        logger.debug("Pool stored connection to %s:%s (pool size=%d)", ip, port, len(self._pool))

    def drain(self) -> None:
        """Disconnect all pooled connections. Called on worker shutdown."""
        logger.info("Draining connection pool (%d connections)", len(self._pool))
        for key in list(self._pool):
            self._evict(key)

    def _evict(self, key: tuple) -> None:
        entry = self._pool.pop(key, None)
        if entry is not None:
            try:
                entry.connection.disconnect()
            except Exception:
                pass


# Module-level singleton — one pool per worker process
pool = ConnectionPool()
