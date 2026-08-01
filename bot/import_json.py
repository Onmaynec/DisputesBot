from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .database import Database
from .sql_profile_store import SQLProfileStore
from .storage import MemoryStore


@dataclass(slots=True)
class ImportReport:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0


def parse_legacy_profiles(path: Path) -> list[tuple[int, dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Корневой JSON должен быть объектом")
    profiles: list[tuple[int, dict[str, Any]]] = []
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        raw_user_id = value.get("user_id")
        if isinstance(raw_user_id, int):
            user_id = raw_user_id
        elif str(key).isdigit():
            user_id = int(key)
        else:
            continue
        profiles.append((user_id, value))
    return profiles


async def import_profiles(
    repository: SQLProfileStore,
    profiles: list[tuple[int, dict[str, Any]]],
    *,
    dry_run: bool = False,
) -> ImportReport:
    report = ImportReport()
    seen: set[int] = set()
    for user_id, raw in profiles:
        if user_id in seen:
            report.skipped += 1
            continue
        seen.add(user_id)
        if dry_run:
            report.skipped += 1
            continue
        try:
            created = await repository.import_profile(user_id, raw)
        except (TypeError, ValueError):
            report.errors += 1
            continue
        if created:
            report.created += 1
        else:
            report.updated += 1
    return report


async def async_main(args: argparse.Namespace) -> int:
    path = Path(args.path)
    profiles = parse_legacy_profiles(path)
    if args.dry_run:
        print(f"Dry-run: найдено валидных профилей: {len(profiles)}")
        return 0
    database = Database(args.database_url)
    repository = SQLProfileStore(database.sessions, MemoryStore())
    try:
        await database.ping()
        report = await import_profiles(repository, profiles)
    finally:
        await database.close()
    print(
        "Импорт завершён: "
        f"создано={report.created}, обновлено={report.updated}, "
        f"пропущено={report.skipped}, ошибок={report.errors}"
    )
    return int(report.errors > 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import DisputesBot JSON profiles to PostgreSQL")
    parser.add_argument("--path", default="data/leaderboard.json")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        required=os.getenv("DATABASE_URL") is None,
    )
    parser.add_argument("--dry-run", action="store_true")
    raise SystemExit(asyncio.run(async_main(parser.parse_args())))


if __name__ == "__main__":
    main()
