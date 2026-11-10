"""
Test Extras.

Test that apps work without the extras they do not install, and are told which extra to install for the others.
Each test runs in a new process: making a dependency unimportable here would break the other tests.
"""

import subprocess
import sys

import pytest

CODE_WITHOUT_BEANIE = """
import sys
import types

sys.modules["beanie"] = None  # `import beanie` fails, as when the extra is not installed
# `sap.tests.rest` tests the app at `AppMain.asgi`, which in this repository uses beanie.
sys.modules["AppMain.asgi"] = types.SimpleNamespace(app=None)

import sap.fastapi.auth
import sap.fastapi.cache
import sap.fastapi.middleware
import sap.fastapi.pagination
import sap.tests.rest
from sap.fastapi.serializers import ObjectSerializer


class Item:
    public_id = "item_1"


assert ObjectSerializer.get_id(Item()) == "item_1"
assert "sap.beanie" not in sys.modules
"""


def run_python(code: str) -> subprocess.CompletedProcess[str]:
    """Run the code in a new Python process."""
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)


def test_fastapi_works_without_beanie() -> None:
    """Import the FastAPI and REST test helpers and serialize an object when beanie cannot be imported."""
    result = run_python(CODE_WITHOUT_BEANIE)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "module, dependency, extra",
    [
        ("sap.beanie", "beanie", "beanie"),
        ("sap.beanie.tests", "beanie", "beanie"),
        ("sap.worker.taskiq", "taskiq", "taskiq"),
        ("sap.worker.celery", "celery", "celery"),
    ],
)
def test_missing_extra_is_named(module: str, dependency: str, extra: str) -> None:
    """Name the extra to install when a module needs one that is not installed."""
    result = run_python(f"import sys; sys.modules[{dependency!r}] = None; import {module}")
    assert result.returncode == 1
    assert f"needs the {extra} extra: pip install 'sapx[{extra}]'" in result.stderr
