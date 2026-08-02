import importlib
import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiogram") is None,
    reason="aiogram is installed in CI and production dependencies",
)


def test_application_imports_all_routers() -> None:
    module = importlib.import_module("bot.main")

    assert module.v17_router.name == "v17"
    assert module.v16_router.name == "v16"
    assert module.v15_router.name == "v15"
    assert module.v14_router.name == "v14"
    assert module.v13_router.name == "v13"
    assert module.v11_router.name == "v11"
    assert module.v10_router.name == "v10"
    assert module.v09_router.name == "v09"
    assert module.v08_router.name == "v08"
    assert module.v07_router.name == "v07"
    assert module.v06_router.name == "v06"
    assert module.v05_router.name == "v05"
    assert module.v04_router.name == "v04"
