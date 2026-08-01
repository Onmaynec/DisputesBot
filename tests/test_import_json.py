import json
from pathlib import Path

import pytest

from bot.import_json import import_profiles, parse_legacy_profiles


def test_parser_accepts_v02_and_v03_keys(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            {
                "123": {"username": "numeric"},
                "@legacy": {"user_id": 456, "username": "legacy"},
                "broken": {"username": "skip"},
            }
        ),
        encoding="utf-8",
    )

    parsed = parse_legacy_profiles(path)

    assert [item[0] for item in parsed] == [123, 456]


class FakeRepository:
    def __init__(self) -> None:
        self.ids: set[int] = set()

    async def import_profile(self, user_id: int, raw: dict[str, object]) -> bool:
        created = user_id not in self.ids
        self.ids.add(user_id)
        return created


@pytest.mark.asyncio
async def test_import_is_idempotent() -> None:
    repository = FakeRepository()
    profiles = [(1, {"user_id": 1}), (2, {"user_id": 2})]

    first = await import_profiles(repository, profiles)  # type: ignore[arg-type]
    second = await import_profiles(repository, profiles)  # type: ignore[arg-type]

    assert first.created == 2
    assert second.updated == 2
