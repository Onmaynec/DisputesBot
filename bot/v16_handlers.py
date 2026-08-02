from aiogram import Router

from .season_insight_commands import router as season_insight_router

router = Router(name="v16")
router.include_router(season_insight_router)
