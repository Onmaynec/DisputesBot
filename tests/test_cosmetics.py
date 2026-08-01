from bot.cosmetics import (
    COSMETIC_CATALOG,
    CosmeticKind,
    cosmetic_by_id,
    cosmetics_by_kind,
)


def test_cosmetic_catalog_has_unique_ids_and_positive_prices() -> None:
    ids = [item.item_id for item in COSMETIC_CATALOG]

    assert len(ids) == len(set(ids))
    assert all(item.price_tokens > 0 for item in COSMETIC_CATALOG)
    assert all(item.required_points >= 0 for item in COSMETIC_CATALOG)


def test_cosmetic_lookup_normalizes_id() -> None:
    item = cosmetic_by_id("  SHARP_MIND ")

    assert item is not None
    assert item.kind is CosmeticKind.TITLE
    assert item.display == "Острый ум"
    assert cosmetic_by_id("missing") is None
    assert cosmetic_by_id(None) is None


def test_catalog_contains_titles_and_badges() -> None:
    titles = cosmetics_by_kind(CosmeticKind.TITLE)
    badges = cosmetics_by_kind(CosmeticKind.BADGE)

    assert len(titles) == 4
    assert len(badges) == 4
    assert {item.kind for item in titles} == {CosmeticKind.TITLE}
    assert {item.kind for item in badges} == {CosmeticKind.BADGE}
