from aiogram import Router

from .pvp_invites import router as invites_router
from .pvp_match_commands import router as match_router
from .pvp_queue_commands import router as queue_router
from .pvp_rating_commands import router as rating_router

router = Router(name="pvp-commands")
router.include_router(invites_router)
router.include_router(queue_router)
router.include_router(match_router)
router.include_router(rating_router)
