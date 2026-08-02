from bot.coaching_models import CoachingResult, CoachingSkill, SkillScores


def test_skill_scores_select_stable_strength_and_focus() -> None:
    scores = SkillScores(logic=8.0, evidence=5.0, rebuttal=8.0)

    assert scores.total == 21.0
    assert scores.strongest_skill is CoachingSkill.LOGIC
    assert scores.focus_skill is CoachingSkill.EVIDENCE


def test_coaching_metadata_is_user_facing() -> None:
    for skill in CoachingSkill:
        assert skill.label
        assert skill.icon
        assert len(skill.advice) > 40

    assert CoachingResult.WIN.label == "Победа"
    assert CoachingResult.DRAW.icon == "🤝"
    assert CoachingResult.LOSS.label == "Поражение"
