"""Ensure every API endpoint has a spectree response annotation.

Prevents new endpoints from being added without OpenAPI documentation.
"""

import inspect

from naas.resources.api_keys import ApiKey, ApiKeyRotate, ApiKeys
from naas.resources.cancel_job import CancelJob
from naas.resources.contexts import Contexts
from naas.resources.failed_jobs import FailedJobs, ReplayJob
from naas.resources.get_results import GetResults
from naas.resources.healthcheck import HealthCheck
from naas.resources.list_jobs import ListJobs
from naas.resources.send_command import SendCommand
from naas.resources.send_command_structured import SendCommandStructured
from naas.resources.send_config import SendConfig

# Every Resource class and the HTTP methods that MUST have spec.validate
_RESOURCE_METHODS: list[tuple[type, list[str]]] = [
    (HealthCheck, ["get"]),
    (SendCommand, ["post"]),
    (SendCommandStructured, ["post"]),
    (SendConfig, ["post"]),
    (GetResults, ["get"]),
    (ListJobs, ["get"]),
    (FailedJobs, ["get"]),
    (ReplayJob, ["post"]),
    (CancelJob, ["delete"]),
    (Contexts, ["get"]),
    (ApiKeys, ["get", "post"]),
    (ApiKey, ["delete"]),
    (ApiKeyRotate, ["post"]),
]


def _has_spectree(func: object) -> bool:
    """Check if a function is decorated with spec.validate."""
    for attr in dir(func):
        if "spectree" in attr.lower():
            return True
    if hasattr(func, "__wrapped__"):
        return True
    try:
        source = inspect.getsource(func)  # type: ignore[arg-type]
        return "spec.validate" in source
    except (TypeError, OSError):
        return False


class TestSpectreeAnnotations:
    """Every resource method must have a spectree resp= annotation."""

    def test_all_endpoints_have_spectree_annotation(self) -> None:
        missing: list[str] = []
        for resource_cls, methods in _RESOURCE_METHODS:
            for method_name in methods:
                func = getattr(resource_cls, method_name, None)
                if func is None:
                    missing.append(f"{resource_cls.__name__}.{method_name} (method not found)")
                    continue
                if not _has_spectree(func):
                    missing.append(f"{resource_cls.__name__}.{method_name}")

        assert not missing, (
            "Endpoints missing spec.validate annotation:\n"
            + "\n".join(f"  - {m}" for m in missing)
            + "\n\nAdd @spec.validate(resp=Response(...)) to these methods."
        )

    def test_resource_registry_is_complete(self) -> None:
        """Ensure _RESOURCE_METHODS covers all resource classes.

        If you add a new Resource, add it to _RESOURCE_METHODS above.
        """
        import pkgutil

        import naas.resources as res_pkg

        registered_names = {cls.__name__ for cls, _ in _RESOURCE_METHODS}

        for _importer, modname, _ispkg in pkgutil.iter_modules(res_pkg.__path__):
            mod = __import__(f"naas.resources.{modname}", fromlist=[modname])
            from flask_restful import Resource

            for name, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, Resource) and obj is not Resource:
                    assert name in registered_names, (
                        f"Resource class '{name}' in naas.resources.{modname} "
                        f"is not in test_spectree_coverage._RESOURCE_METHODS. "
                        f"Add it with its HTTP methods."
                    )
