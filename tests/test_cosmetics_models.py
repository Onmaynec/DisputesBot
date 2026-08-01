from bot.cosmetics_models import TITLE_CATALOG, title_by_id


def test_title_catalog_has_unique_ids_and_increasing_requirements() -> None:
    ids = [item.title_id for item in TITLE_CATALOG]
    prices = [item.price_tokens for item in TITLE_CATALOG]
    minimums = [item.minimum_points for item in TITLE_CATALOG]

    assert len(ids) == len(set(ids))
    assert prices == sorted(prices)
    assert minimums == sorted(minimums)
    assert title_by_id(" SHARP_REPLY ") == TITLE_CATALOG[1]
    assert title_by_id("unknown") is None
