from aiogram import Router

from .challenge_commands import router as challenge_router

router = Router(name="v10")
router.include_router(challenge_router)
