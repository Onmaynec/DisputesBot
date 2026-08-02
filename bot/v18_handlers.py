from aiogram import Router

from .season_goal_commands import router as season_goal_router

router = Router(name="v18")
router.include_router(season_goal_router)
