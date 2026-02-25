"""Shared SpecTree instance for OpenAPI spec generation."""

from spectree import SpecTree

spec = SpecTree("flask", title="NAAS - Netmiko As A Service", version="v1", path="apidoc")
