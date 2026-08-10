from __future__ import annotations

import py_compile
from pathlib import Path


def test_cloud_run_entrypoints_compile_before_deployment():
    app = Path(__file__).resolve().parents[1]
    for relative in ("service/main.py", "service/day_three_routes.py"):
        py_compile.compile(str(app / relative), doraise=True)
