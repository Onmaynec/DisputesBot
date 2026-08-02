from aiogram import Router

from .pvp_record_commands import router as pvp_record_router

router = Router(name="v17")
router.include_router(pvp_record_router)
