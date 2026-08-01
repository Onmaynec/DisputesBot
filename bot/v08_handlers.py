from aiogram import Router

from .cosmetics_commands import router as cosmetics_router

router = Router(name="v08")
router.include_router(cosmetics_router)
