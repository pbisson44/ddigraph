import asyncio
import inspect
import sys
import warnings
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

warnings.filterwarnings(
    "ignore",
    message=r"'asyncio\.iscoroutinefunction' is deprecated and slated for removal in Python 3\.16",
    category=DeprecationWarning,
    module=r"neo4j\._warnings",
)


def pytest_pyfunc_call(pyfuncitem: Any) -> bool | None:
    testfunction = pyfuncitem.obj
    if inspect.iscoroutinefunction(testfunction):
        fixture_info = getattr(pyfuncitem, "_fixtureinfo", None)
        fixture_names = fixture_info.argnames if fixture_info is not None else ()
        kwargs = {name: pyfuncitem.funcargs[name] for name in fixture_names}
        asyncio.run(testfunction(**kwargs))
        return True

    return None
