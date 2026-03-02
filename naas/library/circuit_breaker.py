"""Redis-backed circuit breaker for per-device connection failure tracking."""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

import netmiko
import pybreaker
from paramiko import ssh_exception
from redis import Redis

from naas.config import (
    CIRCUIT_BREAKER_THRESHOLD,
    CIRCUIT_BREAKER_TIMEOUT,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
)
from naas.library.audit import emit_audit_event
from naas.library.auth import device_lockout

if TYPE_CHECKING:
    pass

logger = logging.getLogger(name="NAAS")

# Per-device circuit breakers (lazily populated)
_circuit_breakers: dict[str, pybreaker.CircuitBreaker] = {}
_redis_client: Redis | None = None


def _get_redis() -> Redis:
    """Lazily initialise the shared Redis client for circuit breaker storage."""
    global _redis_client
    if _redis_client is None:  # pragma: no cover  # tests inject fakeredis before first call
        _redis_client = Redis(host=REDIS_HOST, port=int(REDIS_PORT), password=REDIS_PASSWORD)
    return _redis_client


class RedisCircuitBreakerStorage(pybreaker.CircuitBreakerStorage):
    """Redis-backed storage for circuit breaker state shared across workers."""

    def __init__(self, name: str, redis_client: Redis):
        super().__init__(name)
        self.redis = redis_client
        self._key = f"circuit_breaker:{name}"

    @property
    def state(self) -> str:
        """Get current circuit state."""
        val = self.redis.hget(self._key, "state")
        return val.decode() if isinstance(val, bytes) else (val or "closed")  # type: ignore[return-value]  # redis stubs type hget as Awaitable[str|None]|str; sync client always returns str|None

    @state.setter
    def state(self, state: str) -> None:
        """Set current circuit state."""
        self.redis.hset(self._key, "state", state)

    def increment_counter(self) -> None:
        """Increment failure counter."""
        self.redis.hincrby(self._key, "counter", 1)

    def reset_counter(self) -> None:
        """Reset failure counter."""
        self.redis.hset(self._key, "counter", str(0))

    def increment_success_counter(self) -> None:
        """Increment success counter."""
        self.redis.hincrby(self._key, "success_counter", 1)

    def reset_success_counter(self) -> None:
        """Reset success counter."""
        self.redis.hset(self._key, "success_counter", str(0))

    @property
    def counter(self) -> int:
        """Get failure counter."""
        val = self.redis.hget(self._key, "counter")
        return int(val) if val else 0  # type: ignore[arg-type]  # redis stubs type hget as Awaitable[str|None]|str; sync client always returns str|None

    @property
    def success_counter(self) -> int:
        """Get success counter."""
        val = self.redis.hget(self._key, "success_counter")
        return int(val) if val else 0  # type: ignore[arg-type]  # redis stubs type hget as Awaitable[str|None]|str; sync client always returns str|None

    @property
    def opened_at(self) -> datetime | None:
        """Get when circuit was opened."""
        val = self.redis.hget(self._key, "opened_at")
        if not val:
            return None  # pragma: no cover  # opened_at is only set when circuit opens; tests reset state between runs
        return datetime.fromisoformat(val.decode() if isinstance(val, bytes) else val)  # type: ignore[arg-type]  # redis stubs type hget as Awaitable[str|None]|str; sync client always returns str|None

    @opened_at.setter
    def opened_at(self, dt: datetime) -> None:
        """Set when circuit was opened."""
        self.redis.hset(self._key, "opened_at", dt.isoformat())


def _get_circuit_breaker(device_id: str) -> pybreaker.CircuitBreaker:
    """Get or create a circuit breaker for a specific device."""
    if device_id not in _circuit_breakers:
        storage = RedisCircuitBreakerStorage(f"device_{device_id}", _get_redis())
        breaker = pybreaker.CircuitBreaker(
            fail_max=CIRCUIT_BREAKER_THRESHOLD,
            reset_timeout=CIRCUIT_BREAKER_TIMEOUT,
            name=f"device_{device_id}",
            state_storage=storage,
        )

        class AuditListener(pybreaker.CircuitBreakerListener):
            def state_change(self, cb, old_state, new_state):
                if new_state.name == "open":
                    emit_audit_event("circuit.opened", ip=device_id)
                elif new_state.name == "closed" and old_state and old_state.name == "open":  # pragma: no cover
                    emit_audit_event("circuit.closed", ip=device_id)

        breaker.add_listener(AuditListener())

        _circuit_breakers[device_id] = breaker
    return _circuit_breakers[device_id]


def with_circuit_breaker(ip: str, request_id: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call fn through the circuit breaker for the given device IP.

    Handles CircuitBreakerError, timeout, and SSH errors uniformly,
    recording device lockout failures on each. Auth failures are NOT
    routed through here — they are handled inside the impl functions
    and do not trigger the circuit breaker.

    :return: The return value of fn, or (None, error_str) on failure.
    """
    breaker = _get_circuit_breaker(ip)
    try:
        return breaker.call(fn, *args, **kwargs)  # type: ignore[no-any-return]  # pybreaker.call() returns Any; no stubs available
    except pybreaker.CircuitBreakerError:
        logger.warning("%s %s:Circuit breaker open, rejecting connection attempt", request_id, ip)
        device_lockout(ip=ip, report_failure=True)
        return None, f"Circuit breaker open for device {ip} - too many recent failures"
    except (TimeoutError, netmiko.NetMikoTimeoutException) as e:
        device_lockout(ip=ip, report_failure=True)
        return None, str(e)
    except (ssh_exception.SSHException, ValueError) as e:
        device_lockout(ip=ip, report_failure=True)
        return None, f"Unknown SSH error connecting to device {ip}: {str(e)}"
