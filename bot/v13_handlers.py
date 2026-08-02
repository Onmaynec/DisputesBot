from aiogram import Router

from .coaching_commands import router as coaching_router

router = Router(name="v13")
router.include_router(coaching_router)
