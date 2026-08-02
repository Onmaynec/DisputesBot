from aiogram import Router

from .season_pass_commands import router as season_pass_router

router = Router(name="v20")
router.include_router(season_pass_router)
