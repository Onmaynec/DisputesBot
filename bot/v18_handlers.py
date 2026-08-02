from aiogram import Router

from .season_goal_commands import router as season_goal_router
from .v19_handlers import router as v19_router

router = Router(name="v18")
router.include_router(v19_router)
router.include_router(season_goal_router)
