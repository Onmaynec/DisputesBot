from aiogram import Router

from .league_commands import router as league_router

router = Router(name="v10")
router.include_router(league_router)
