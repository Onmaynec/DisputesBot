from aiogram import Router

from .cosmetic_commands import router as cosmetic_router

router = Router(name="v08")
router.include_router(cosmetic_router)
