from aiogram import Router

from .season_archive_commands import router as season_archive_router

router = Router(name="v15")
router.include_router(season_archive_router)
