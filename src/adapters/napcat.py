# src/adapters/napcat.py (最终修正版 v6.1)
import asyncio
import websockets
import json
import time
from typing import Dict, Any, Optional, TYPE_CHECKING, Set

from ..logger import logger
from ..event import BaseEvent, MessageEvent, PrivateMessageEvent, GroupMessageEvent
from ..message import Message, MessageSegment
from ..matcher import Matcher # <--- 确保导入了 Matcher
from .base import Adapter # <--- 确保导入了 Adapter 基类

if TYPE_CHECKING:
    from ..bot import Bot

_adapter_instance: Optional["NapcatAdapter"] = None

# --- 这是最关键的 handler，它只接收一个参数！---
async def global_ws_handler(websocket: websockets.WebSocketServerProtocol):
    """
    这个 handler 只接收一个参数，完全匹配报错信息的调用方式！
    """
    global _adapter_instance
    if not _adapter_instance:
        logger.error("全局 Adapter 实例未设置，无法处理连接！")
        return

    client_addr = websocket.remote_address
    logger.info(f"Napcat 客户端已连接: {client_addr}")
    _adapter_instance.connections.add(websocket)

    try:
        # --- 核心修改点在这里！ ---
        async for raw_event_str in websocket: # 使用 async for 循环，更健壮
            try:
                raw_event_dict = json.loads(raw_event_str)
            except json.JSONDecodeError:
                logger.error(f"解析 Napcat 事件 JSON 失败: {raw_event_str}")
                continue

            # 1. 净化与认知：将原始事件转换为我们自己的 DaY-Core Event
            day_event = _adapter_instance._convert_to_day_event(raw_event_dict)

            if day_event:
                logger.info(f"[DAY-CORE EVENT] {day_event!r}")
                # 2. 神经分发：将纯洁的 Event 交给 Matcher 系统处理！
                # 我们把 bot 和 adapter 自身都传进去
                # _adapter_instance 就是 NapcatAdapter 的实例，它继承了 Adapter
                # _adapter_instance.bot 就是 Bot 的实例
                await Matcher.run_all(
                    bot=_adapter_instance.bot,
                    adapter=_adapter_instance,
                    event=day_event
                )
            else:
                # 对于非消息事件（比如心跳），我们暂时只打印日志
                logger.debug(f"[OTHER RAW EVENT] {raw_event_str}")
        # --- 修改结束 ---

    except websockets.ConnectionClosed:
        logger.warning(f"Napcat 客户端 {client_addr} 连接已断开。")
    except Exception as e:
        logger.error(f"处理 Napcat 客户端 {client_addr} 时出错: {e}", exc_info=True)
    finally:
        if _adapter_instance:
            _adapter_instance.connections.remove(websocket)
        logger.info(f"与 Napcat 客户端 {client_addr} 的会话结束。")


# --- NapcatAdapter 类也需要修改 ---
class NapcatAdapter(Adapter): # <--- 确保继承了我们定义的 Adapter 基类
    def __init__(self, bot_instance: "Bot"):
        global _adapter_instance
        self.bot = bot_instance
        self.host = self.bot.config.adapter_host
        self.port = self.bot.config.adapter_port
        self._server_task: Optional[asyncio.Task] = None
        self.connections: Set[websockets.WebSocketServerProtocol] = set()
        _adapter_instance = self

    def _convert_to_day_event(self, raw_event: Dict[str, Any]) -> Optional[BaseEvent]:
        post_type = raw_event.get("post_type")
        if post_type == "message":
            message_type = raw_event.get("message_type")
            common_data = {
                "self_id": str(raw_event.get("self_id")),
                "sub_type": raw_event.get("sub_type", ""),
                "message_id": str(raw_event.get("message_id")),
                "message": self._parse_message_segments(raw_event.get("message", [])),
                "raw_message": raw_event.get("raw_message", ""),
                "user_id": str(raw_event.get("user_id")),
                "time": int(raw_event.get("time", time.time())),
            }
            if message_type == "private":
                return PrivateMessageEvent(**common_data)
            elif message_type == "group":
                return GroupMessageEvent(group_id=str(raw_event.get("group_id")), **common_data)
        return None

    def _parse_message_segments(self, napcat_segments: list) -> Message:
        day_segments = []
        for seg_data in napcat_segments:
            seg_type = seg_data.get("type", "unknown")
            data = seg_data.get("data", {})
            day_segments.append(MessageSegment(type=seg_type, data=data))
        return Message(day_segments)

    # --- 实现 send_message 方法 ---
    async def send_message(self, conversation_id: str, message_type: str, message: Message) -> Any:
        """向 Napcat 发送消息。"""
        logger.info(f"准备向 {message_type}:{conversation_id} 发送消息: {message.get_plain_text()}")

        if not self.connections:
            logger.error("发送消息失败：没有可用的 Napcat 连接。")
            return None

        # 随便拿一个连接用
        conn = next(iter(self.connections))

        napcat_segs = []
        for seg in message:
            napcat_segs.append({"type": seg.type, "data": seg.data})

        action = ""
        params = {"message": napcat_segs}
        if message_type == "group":
            action = "send_group_msg"
            params["group_id"] = int(conversation_id)
        elif message_type == "private":
            action = "send_private_msg"
            params["user_id"] = int(conversation_id)

        if not action:
            logger.error(f"未知的 message_type: {message_type}")
            return None

        # 使用 echo 来追踪响应，这是一个好习惯！
        echo = f"day-core-send-{time.time_ns()}"
        payload = {
            "action": action,
            "params": params,
            "echo": echo
        }

        try:
            await conn.send(json.dumps(payload))
            logger.info(f"消息已通过 WebSocket 发送至 Napcat (echo: {echo})。")
            # 在真实的框架中，这里会等待并返回 Napcat 的响应，但现在我们先假设它成功了
            return {"status": "ok", "echo": echo}
        except Exception as e:
            logger.error(f"通过 WebSocket 发送消息失败: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    async def run(self):
        logger.info("Napcat 使徒 (服务器模式) 已准备就绪，开门迎客！")
        server = await websockets.serve(global_ws_handler, self.host, self.port)
        logger.info(f"DaY-Core (作为服务器) 正在启动，监听地址 ws://{self.host}:{self.port}")

        async def server_shutdown_wrapper():
            try:
                await asyncio.Future()
            finally:
                logger.info("服务器正在关闭所有连接...")
                server.close()
                await server.wait_closed()

        self._server_task = asyncio.create_task(server_shutdown_wrapper())

    async def stop(self):
        logger.info("Napcat 使徒 (服务器模式) 正在关门谢客...")
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
        logger.info("服务器任务已停止。")