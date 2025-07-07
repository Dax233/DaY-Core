# src/adapters/napcat.py (版本修正・返璞归真版 v6.0)
import asyncio
import websockets
import json
import time
from typing import Dict, Any, Optional, TYPE_CHECKING, Set

from ..logger import logger
from ..event import BaseEvent, MessageEvent, PrivateMessageEvent, GroupMessageEvent
from ..message import Message, MessageSegment

if TYPE_CHECKING:
    from ..bot import Bot

# --- 我们把 Adapter 的实例变成一个全局变量，让 handler 能访问到它 ---
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
        while True:
            raw_event_str = await websocket.recv()
            try:
                raw_event_dict = json.loads(raw_event_str)
            except json.JSONDecodeError:
                logger.error(f"解析 Napcat 事件 JSON 失败: {raw_event_str}")
                continue

            day_event = _adapter_instance._convert_to_day_event(raw_event_dict)

            if day_event:
                logger.info(f"[DAY-CORE EVENT] {day_event!r}")
            else:
                logger.debug(f"[OTHER RAW EVENT] {raw_event_str}")

    except websockets.ConnectionClosed:
        logger.warning(f"Napcat 客户端 {client_addr} 连接已断开。")
    except Exception as e:
        logger.error(f"处理 Napcat 客户端 {client_addr} 时出错: {e}", exc_info=True)
    finally:
        if _adapter_instance:
            _adapter_instance.connections.remove(websocket)
        logger.info(f"与 Napcat 客户端 {client_addr} 的会话结束。")


class NapcatAdapter:
    def __init__(self, bot_instance: "Bot"):
        global _adapter_instance
        self.bot = bot_instance
        self.host = "127.0.0.1"
        self.port = 7094
        self._server_task: Optional[asyncio.Task] = None
        self.connections: Set[websockets.WebSocketServerProtocol] = set()
        _adapter_instance = self # 把自己赋值给全局变量

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

    async def run(self):
        logger.info("Napcat 使徒 (服务器模式) 已准备就绪，开门迎客！")
        # 直接把全局 handler 传给 serve
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