# src/bot.py
import asyncio
import json # <-- 需要导入 json
from .logger import logger
from .adapters.napcat import NapcatAdapter
from .plugin import PluginManager
from .config import get_config
from .queue import raw_event_queue # <-- 导入队列
from .api import resolve_response # <-- 导入响应处理器
from .matcher import Matcher # <-- 导入 Matcher

class Bot:
    def __init__(self):
        self.config = get_config()
        self.adapter = NapcatAdapter(self)
        self.plugin_manager = PluginManager(self)
        self._event_processor_task: asyncio.Task | None = None # <-- 用于存放我们的新任务

    # --- 新增一个方法：事件处理器循环！ ---
    async def _event_processor(self):
        logger.info("事件处理器已启动，正在等待处理中转站的消息...")
        while True:
            try:
                # 从队列里取出原始数据
                raw_event_str = await raw_event_queue.get()
                
                try:
                    raw_event_dict = json.loads(raw_event_str)
                except json.JSONDecodeError:
                    logger.error(f"事件处理器：解析 JSON 失败: {raw_event_str}")
                    continue

                # 在这里做之前接待员做的工作：判断是事件还是响应
                if raw_event_dict.get("post_type"):
                    day_event = self.adapter._convert_to_day_event(raw_event_dict)
                    if day_event:
                        # 分发给 Matcher 时，需要 bot 和 adapter 实例
                        # 我们在这里创建 Matcher.run_all 的任务，让它并发执行
                        # 这样即使一个 handler 阻塞了，也不会影响处理下一个事件
                        asyncio.create_task(Matcher.run_all(self, self.adapter, day_event))
                elif raw_event_dict.get("echo"):
                    resolve_response(raw_event_dict)
                else:
                    logger.debug(f"事件处理器：收到未知类型数据: {raw_event_dict}")

            except Exception as e:
                logger.error(f"事件处理器发生未知错误: {e}", exc_info=True)


    async def run(self):
        logger.info("Bot 核心已启动...")
        self.plugin_manager.load_all_plugins()
        
        # --- 启动我们的新任务！ ---
        self._event_processor_task = asyncio.create_task(self._event_processor())
        
        logger.info("正在命令 Napcat 使徒出击...")
        await self.adapter.run()

    async def stop(self):
        logger.info("Bot 核心收到停止信号...")
        
        # --- 停止时也要优雅地取消新任务 ---
        if self._event_processor_task and not self._event_processor_task.done():
            self._event_processor_task.cancel()
            try:
                await self._event_processor_task
            except asyncio.CancelledError:
                logger.info("事件处理器任务已取消。")

        logger.info("正在召回 Napcat 使徒...")
        await self.adapter.stop()