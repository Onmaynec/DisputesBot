from bot.challenge_database import PvPChallengeRow
from bot.database import Base


def test_challenge_table_is_registered() -> None:
    assert PvPChallengeRow.__tablename__ == "pvp_challenges"
    assert "pvp_challenges" in Base.metadata.tables
    table = Base.metadata.tables["pvp_challenges"]
    assert {"challenge_id", "challenger_id", "target_id", "status", "expires_at"} <= set(
        table.columns.keys()
    )
