from aiogram import Router

from .goal_reward_commands import router as goal_reward_router

router = Router(name="v19")
router.include_router(goal_reward_router)
