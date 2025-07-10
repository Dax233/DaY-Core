# src/bot.py
import asyncio
import json  # <-- 需要导入 json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .adapters.napcat import NapcatAdapter
from .api import resolve_response  # <-- 导入响应处理器
from .config import get_config
from .database.models import Base, MessageRecord
from .event import BaseEvent, MessageEvent
from .logger import logger
from .matcher import Matcher, _shutdown_hooks, _startup_hooks
from .plugin import PluginManager
from .queue import raw_event_queue  # <-- 导入队列


class Bot:
    """Bot 核心类，负责管理适配器、插件和事件处理."""

    def __init__(self) -> None:
        self.config = get_config()
        self._event_processor_task: asyncio.Task | None = None
        self.background_tasks: set[asyncio.Task] = set()

        # --- 在这里初始化所有属性！ ---
        self.startup_hooks: list[callable] = []
        self.shutdown_hooks: list[callable] = []
        self.db_engine = None
        self.db_session_factory: sessionmaker | None = None

        # --- 实例化其他组件 ---
        self.adapter = NapcatAdapter(self)
        self.plugin_manager = PluginManager(self)
        self.plugin_manager.load_all_plugins()

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
                        # 在分发给 Matcher 之前，执行核心的消息记录逻辑
                        self._log_message_if_enabled(day_event)
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

        # 1. 初始化核心服务（如数据库）
        self._init_database()

        # 2. 从全局列表加载钩子
        self._load_hooks()

        # 3. 执行所有插件注册的启动钩子
        logger.info("正在执行启动钩子...")
        for hook in self.startup_hooks:
            # 调用钩子时，可以像依赖注入一样，把 bot 实例传进去
            await hook()

        # 4. 启动事件处理器
        self._event_processor_task = asyncio.create_task(self._event_processor())

        # 5. 启动适配器
        logger.info("正在命令 Napcat 使徒出击...")
        await self.adapter.run()

    def _load_hooks(self) -> None:
        """从全局列表中加载启动和关闭钩子."""
        self.startup_hooks.extend(_startup_hooks)
        self.shutdown_hooks.extend(_shutdown_hooks)
        logger.info(
            f"已加载 {len(self.startup_hooks)} 个启动钩子和 {len(self.shutdown_hooks)} 个关闭钩子。"
        )

    def _init_database(self) -> None:
        """将数据库初始化作为 Bot 的核心内置方法."""
        if not self.config.logger_enable:
            logger.info("数据库日志记录功能未启用。")
            return

        project_root = Path(__file__).resolve().parent.parent
        db_path = project_root / self.config.logger_database_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        db_url = f"sqlite:///{db_path.resolve()}"
        logger.info(f"数据库日志记录已启用，连接到: {db_url}")

        engine = create_engine(db_url)
        self.db_engine = engine
        self.db_session_factory = sessionmaker(bind=engine)

        Base.metadata.create_all(engine)
        logger.info("数据库表结构已确认。")

    def _log_message_if_enabled(self, event: BaseEvent) -> None:
        """如果数据库功能已启用，则记录消息事件.

        Args:
            event (BaseEvent): 任意事件对象.
        """
        # 只处理消息事件，并且确保数据库已启用
        if not isinstance(event, MessageEvent) or not self.db_session_factory:
            return

        try:
            with self.db_session_factory() as session:
                record = MessageRecord(
                    self_id=event.self_id,
                    message_type=event.message_type,
                    group_id=event.group_id if event.message_type == "group" else None,
                    user_id=event.user_id,
                    # 优先使用群名片，其次是昵称
                    sender_name=(
                        event.sender.get("card") or event.sender.get("nickname", "未知昵称")
                    )
                    if event.sender
                    else "未知发送者",
                    raw_message=event.raw_message,
                )
                session.add(record)
                session.commit()
                logger.debug(f"核心记录器：消息已存入数据库: {record}")
        except Exception as e:
            logger.error(f"核心记录器：写入数据库时发生错误: {e}", exc_info=True)

    async def stop(self) -> None:
        """停止 Bot 的所有服务，并优雅地取消所有任务."""
        logger.info("Bot 核心收到停止信号...")

        # 1. 执行所有关闭钩子
        logger.info("正在执行关闭钩子...")
        for hook in self.shutdown_hooks:
            await hook()

        # 2. 关闭核心服务（如数据库）
        if self.db_engine:
            self.db_engine.dispose()
            logger.info("数据库连接池已关闭。")

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
