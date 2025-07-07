# src/bot.py
import asyncio
from .logger import logger
from .adapters.napcat import NapcatAdapter
from .plugin import PluginManager # 导入插件管理器
from .config import get_config

class Bot:
    def __init__(self):
        self.config = get_config()
        self.adapter = NapcatAdapter(self)
        self.plugin_manager = PluginManager(self) # 创建插件管理器实例

    async def run(self):
        logger.info("Bot 核心已启动...")
        # 在启动 adapter 之前加载所有插件
        self.plugin_manager.load_all_plugins()
        logger.info("正在命令 Napcat 使徒出击...")
        await self.adapter.run()

    async def stop(self):
        logger.info("Bot 核心收到停止信号，正在召回 Napcat 使徒...")
        await self.adapter.stop()