# src/bot.py
import asyncio
from .logger import logger
from .adapters.napcat import NapcatAdapter

class Bot:
    def __init__(self):
        self.adapter = NapcatAdapter(self)

    # run 方法变成 async
    async def run(self):
        logger.info("Bot 核心已启动，正在命令 Napcat 使徒出击...")
        # adapter.run() 也应该是 async
        await self.adapter.run()

    # stop 方法也变成 async
    async def stop(self):
        logger.info("Bot 核心收到停止信号，正在召回 Napcat 使徒...")
        # adapter.stop() 也应该是 async
        await self.adapter.stop()