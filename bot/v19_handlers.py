from aiogram import Router

from .goal_reward_commands import router as goal_reward_router
from .v20_handlers import router as v20_router

router = Router(name="v19")
router.include_router(v20_router)
router.include_router(goal_reward_router)
