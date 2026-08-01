from aiogram import Router

from .progression_commands import router as progression_router

router = Router(name="v07")
router.include_router(progression_router)
