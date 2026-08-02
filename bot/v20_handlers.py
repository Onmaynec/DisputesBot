from aiogram import Router

from .season_pass_commands import router as season_pass_router
from .v21_handlers import router as v21_router

router = Router(name="v20")
router.include_router(v21_router)
router.include_router(season_pass_router)
