# src/bot.py
import asyncio
import json  # <-- 需要导入 json

from .adapters.napcat import NapcatAdapter
from .api import resolve_response  # <-- 导入响应处理器
from .config import get_config
from .logger import logger
from .matcher import Matcher  # <-- 导入 Matcher
from .plugin import PluginManager
from .queue import raw_event_queue  # <-- 导入队列


class Bot:
    """Bot 核心类，负责管理适配器、插件和事件处理."""

    def __init__(self) -> None:
        self.config = get_config()
        self.adapter = NapcatAdapter(self)
        self.plugin_manager = PluginManager(self)
        self._event_processor_task: asyncio.Task | None = None
        self.background_tasks: set[asyncio.Task] = set()

    # --- 新增一个方法：事件处理器循环！ ---
    async def _event_processor(self) -> None:
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
                        task = asyncio.create_task(Matcher.run_all(self, self.adapter, day_event))
                        # 将新创建的任务添加到我们的“控制中心”
                        self.background_tasks.add(task)
                        # 我们再给任务绑定一个“完成回调”，当任务执行完毕后，
                        # 自动把它从“控制中心”里移除，避免内存泄漏！
                        task.add_done_callback(self.background_tasks.discard)
                elif raw_event_dict.get("echo"):
                    resolve_response(raw_event_dict)
                else:
                    logger.debug(f"事件处理器：收到未知类型数据: {raw_event_dict}")

            except Exception as e:
                logger.error(f"事件处理器发生未知错误: {e}", exc_info=True)

    async def run(self) -> None:
        """启动 Bot 的所有服务."""
        logger.info("Bot 核心已启动...")
        self.plugin_manager.load_all_plugins()

        # --- 启动我们的新任务！ ---
        self._event_processor_task = asyncio.create_task(self._event_processor())

        logger.info("正在命令 Napcat 使徒出击...")
        await self.adapter.run()

    async def stop(self) -> None:
        """停止 Bot 的所有服务，并优雅地取消所有任务."""
        logger.info("Bot 核心收到停止信号...")

        # --- 停止时也要优雅地取消新任务 ---
        if self._event_processor_task and not self._event_processor_task.done():
            self._event_processor_task.cancel()
            try:
                await self._event_processor_task
            except asyncio.CancelledError:
                logger.info("事件处理器任务已取消。")

        logger.info(f"正在取消 {len(self.background_tasks)} 个正在运行的后台事件任务...")
        if self.background_tasks:
            # 创建一个任务列表的副本进行迭代，因为集合在迭代时不能被修改
            tasks_to_cancel = list(self.background_tasks)
            for task in tasks_to_cancel:
                task.cancel()
            # 等待所有任务都被成功取消
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            logger.info("所有后台事件任务已取消。")

        logger.info("正在召回 Napcat 使徒...")
        await self.adapter.stop()
