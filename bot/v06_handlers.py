from aiogram import Router

from .moderation_commands import router as moderation_router
from .pvp_rematch import router as rematch_router

router = Router(name="v06")
router.include_router(rematch_router)
router.include_router(moderation_router)
