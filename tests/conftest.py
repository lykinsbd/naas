import pytest
from fakeredis import FakeRedis


@pytest.fixture
def fake_redis():
    """Provide a fake Redis instance for testing (no decode for binary data)."""
    return FakeRedis()
