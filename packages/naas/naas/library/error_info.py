"""Structured error metadata for job results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ErrorInfo:
    """Machine-parseable error classification attached to job results."""

    message: str
    code: str
    retryable: bool
