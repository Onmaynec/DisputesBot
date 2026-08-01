from aiogram import Router

from .social_commands import router as social_router

router = Router(name="v09")
router.include_router(social_router)
