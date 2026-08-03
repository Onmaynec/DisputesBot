from aiogram import Router

from .v22_handlers import router as v22_router

router = Router(name="v21")
router.include_router(v22_router)
