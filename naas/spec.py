"""Shared SpecTree instance for OpenAPI spec generation."""

from spectree import SpecTree
from spectree.config import SecurityScheme
from spectree.models import SecureType, SecuritySchemeData

spec = SpecTree(
    "flask",
    title="NAAS - Netmiko As A Service",
    version="v1",
    path="apidoc",
    security_schemes=[
        SecurityScheme(
            name="basicAuth",
            data=SecuritySchemeData(type=SecureType.HTTP, scheme="basic"),  # type: ignore[call-arg]
        )
    ],
    security=[{"basicAuth": []}],
)
