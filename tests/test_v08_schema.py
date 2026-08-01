from bot.database import Base


def test_v08_title_tables_are_registered() -> None:
    tables = Base.metadata.tables

    assert "pvp_title_purchases" in tables
    assert "pvp_title_loadouts" in tables
    assert "ix_pvp_title_purchases_season_title" in {
        index.name
        for index in tables["pvp_title_purchases"].indexes
    }
