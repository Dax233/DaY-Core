# src/bot.py
import asyncio
import json  # <-- 需要导入 json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .adapters.napcat import NapcatAdapter
from .api import resolve_response  # <-- 导入响应处理器
from .config import get_config
from .database.models import Base, EventRecord
from .event import (
    BaseEvent,
    FriendAddRequestEvent,
    GroupAddRequestEvent,
    GroupMessageEvent,
    HeartbeatEvent,
    LifecycleEvent,
    MessageEvent,
    NoticeEvent,
    PrivateMessageEvent,
)
from .logger import logger
from .matcher import Matcher, _shutdown_hooks, _startup_hooks
from .message import Message
from .plugin import PluginManager
from .queue import raw_event_queue  # <-- 导入队列


class Bot:
    """Bot 核心类，负责管理适配器、插件和事件处理."""

    def __init__(self) -> None:
        self.config = get_config()
        self._event_processor_task: asyncio.Task | None = None
        self.background_tasks: set[asyncio.Task] = set()

        # --- 在这里初始化所有属性！ ---
        self.startup_hooks: list[Callable] = []
        self.shutdown_hooks: list[Callable] = []
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
                        self._handle_event(day_event)
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
            try:
                await hook()
            except Exception as e:
                logger.exception(
                    f"启动钩子 {getattr(hook, '__name__', str(hook))} 执行时发生异常: {e}"
                )

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

    def _log_pretty_event(self, event: BaseEvent) -> None:
        """将事件以易于阅读的格式打印到日志."""
        log_message = ""
        if isinstance(event, GroupMessageEvent):
            sender_name = (
                (event.sender.get("card") or event.sender.get("nickname", "未知昵称"))
                if event.sender
                else "未知"
            )
            log_message = (
                f"群聊消息 | 群: {event.group_id} | "
                f"用户: {sender_name}({event.user_id}) | "
                f"内容: {event.message.get_plain_text()[:50]}..."
            )
        elif isinstance(event, PrivateMessageEvent):
            sender_name = event.sender.get("nickname", "未知昵称") if event.sender else "未知"
            log_message = (
                f"私聊消息 | 用户: {sender_name}({event.user_id}) | "
                f"内容: {event.message.get_plain_text()[:50]}..."
            )
        elif isinstance(event, NoticeEvent):
            log_message = (
                f"通知事件 | 类型: {event.notice_type} | "
                f"子类型: {getattr(event, 'sub_type', 'N/A')}"
            )
        # 对于心跳事件，我们用 DEBUG 等级，因为它太频繁了，会刷屏
        elif isinstance(event, HeartbeatEvent):
            status = event.status or {}
            online_status = "在线" if status.get("online") else "离线"
            logger.debug(f"元事件 | 心跳 | 状态: {online_status}")
            return  # 直接返回，不走下面的 INFO
        elif isinstance(event, LifecycleEvent):
            log_message = f"元事件 | 生命周期 | 类型: {event.sub_type}"

        # 只有在生成了易读日志时才打印
        if log_message:
            # 我们使用 INFO 级别，因为它比 DEBUG 更重要，是我们想要日常看到的内容
            logger.info(log_message)

    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """一个静态的、可重用的 JSON 序列化辅助函数.

        专门处理我们自定义的 DataClass 和 Message 对象.
        """
        if isinstance(obj, Message):
            # 将 Message 对象转换为其内部列表的字典表示
            return [seg.__dict__ for seg in obj]
        # 对于其他 dataclass 对象，使用其 __dict__
        # 对于无法序列化的类型，返回其字符串表示，避免错误
        return obj.__dict__ if hasattr(obj, "__dict__") else str(obj)

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

    def _log_event_if_enabled(self, event: BaseEvent) -> None:
        """如果数据库功能已启用，则记录事件.

        Args:
            event (BaseEvent): 任意事件对象.
        """
        # 1. 检查总开关
        if not self.db_session_factory:
            return

        # 2. 根据神谕，忽略心跳事件
        if isinstance(event, HeartbeatEvent):
            return

        # 3. 准备写入数据库的数据
        summary = "未知事件"
        event_type = "unknown"
        sub_type = getattr(event, "sub_type", None)
        user_id = getattr(event, "user_id", None)
        group_id = getattr(event, "group_id", None)

        # --- 开始咏唱，为不同事件生成摘要 ---
        if isinstance(event, MessageEvent):
            sender_name = (
                (event.sender.get("card") or event.sender.get("nickname", "未知"))
                if event.sender
                else "未知"
            )
            summary = f"来自 {sender_name}({event.user_id}) 的消息: "
            summary += f"{event.message.get_plain_text()[:50]}..."
            event_type = event.message_type
        elif isinstance(event, FriendAddRequestEvent):
            summary = f"来自 {event.user_id} 的好友请求，验证消息: '{event.comment}'"
            event_type = event.request_type
        elif isinstance(event, GroupAddRequestEvent):
            action = "申请加入" if event.sub_type == "add" else "邀请我加入"
            summary = (
                f"用户 {event.user_id} {action}群 {event.group_id}，验证消息: '{event.comment}'"
            )
            event_type = event.request_type
        elif isinstance(event, NoticeEvent):
            summary = f"收到通知: {event.notice_type}, 子类型: {event.sub_type}"
            event_type = event.notice_type
        elif isinstance(event, LifecycleEvent):
            summary = f"机器人生命周期事件: {event.sub_type}"
            event_type = event.meta_event_type

        details_json = json.dumps(
            event, default=self._json_serializer, ensure_ascii=False, indent=2
        )

        # 5. 写入数据库
        try:
            with self.db_session_factory() as session:
                record = EventRecord(
                    self_id=event.self_id,
                    post_type=event.post_type,
                    event_type=event_type,
                    sub_type=sub_type,
                    group_id=group_id,
                    user_id=user_id,
                    summary=summary,
                    details=details_json,
                )
                session.add(record)
                session.commit()
                logger.debug(f"核心记录器：事件已存入数据库: {record}")
        except Exception as e:
            logger.error(f"核心记录器：写入数据库时发生错误: {e}", exc_info=True)

    def _handle_event(self, event: BaseEvent) -> None:
        """事件分发和核心处理的内部方法."""
        self._log_pretty_event(event)
        # 将所有需要记录的事件都交给记录器处理
        self._log_event_if_enabled(event)

        # 将事件分发给所有匹配的 Matcher
        task = asyncio.create_task(Matcher.run_all(self, self.adapter, event))
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        task.add_done_callback(self._handle_background_task_exception)

    async def stop(self) -> None:
        """停止 Bot 的所有服务，并优雅地取消所有任务."""
        logger.info("Bot 核心收到停止信号...")

        # 1. 执行所有关闭钩子
        logger.info("正在执行关闭钩子...")
        for hook in self.shutdown_hooks:
            try:
                await hook()
            except Exception as e:
                logger.error(f"关闭钩子执行时发生异常: {e}", exc_info=True)

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

    def _handle_background_task_exception(self, task: asyncio.Task) -> None:
        """处理后台任务中的异常并进行日志记录."""
        try:
            exception = task.exception()
            if exception is not None:
                logger.error(f"后台任务异常: {exception}", exc_info=True)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"检查后台任务异常时出错: {e}", exc_info=True)
