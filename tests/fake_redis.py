from __future__ import annotations

from typing import Any


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.sets: dict[str, set[Any]] = {}

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: Any, **kwargs):
        if kwargs.get("nx") and key in self.values:
            return False
        self.values[key] = value
        return True

    async def mget(self, *keys: str):
        return [self.values.get(key) for key in keys]

    async def getdel(self, key: str):
        return self.values.pop(key, None)

    async def delete(self, *keys: str):
        removed = 0
        for key in keys:
            removed += int(key in self.values)
            self.values.pop(key, None)
            self.sets.pop(key, None)
        return removed

    async def sadd(self, key: str, *values: Any):
        target = self.sets.setdefault(key, set())
        before = len(target)
        target.update(values)
        return len(target) - before

    async def srem(self, key: str, *values: Any):
        target = self.sets.setdefault(key, set())
        removed = 0
        for value in values:
            if value in target:
                target.remove(value)
                removed += 1
        return removed

    async def smembers(self, key: str):
        return set(self.sets.get(key, set()))
