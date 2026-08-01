from bot.database import Base
from bot.social_database import PvPProfileSettingRow


def test_v09_profile_settings_table_is_registered() -> None:
    table = Base.metadata.tables["pvp_profile_settings"]

    assert PvPProfileSettingRow.__table__ is table
    assert table.c.is_public.nullable is False
    assert "ix_pvp_profile_settings_public" in {index.name for index in table.indexes}
