from aiogram import Router

from .pvp_commands import router as commands_router
from .pvp_flow import router as flow_router

router = Router(name="v05")
router.include_router(commands_router)
router.include_router(flow_router)
