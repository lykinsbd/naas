"""Tests for worker_metrics module."""

import os
import shutil

from naas.library.worker_metrics import init, make_registry


class TestWorkerMetrics:
    def test_init_creates_dir_and_sets_env(self) -> None:
        path = init()
        try:
            assert os.path.isdir(path)
            assert os.environ["PROMETHEUS_MULTIPROC_DIR"] == path
        finally:
            shutil.rmtree(path, ignore_errors=True)

    def test_make_registry(self) -> None:
        path = init()
        try:
            registry = make_registry()
            assert registry is not None
        finally:
            shutil.rmtree(path, ignore_errors=True)
