# src/adapters/napcat.py (宝宝专用・并发无阻塞最终版 v8.0)
import asyncio
import json
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any, Optional

import websockets

from ..api import API_FAILED, wait_for_response
from ..event import (
    BaseEvent,
    FriendAddRequestEvent,
    GroupAddRequestEvent,
    GroupMemberDecreaseNoticeEvent,
    GroupMemberIncreaseNoticeEvent,
    GroupMessageEvent,
    GroupPokeNoticeEvent,
    NoticeEvent,
    PrivateMessageEvent,
    RequestEvent,
)
from ..logger import logger
from ..message import Message, MessageSegment
from ..queue import raw_event_queue
from .base import Adapter

if TYPE_CHECKING:
    from ..bot import Bot

# 全局的 Adapter 实例，让我们的 websocket handler 能够访问到它
_adapter_instance: Optional["NapcatAdapter"] = None


async def global_ws_handler(websocket: websockets.WebSocketServerProtocol) -> None:
    """这是我们唯一的“接待员”，它的职责被简化到了极致.

    1. 确认身份（有 _adapter_instance 存在）。
    2. 登记连接（把 websocket 连接本身记录下来）。
    3. 接收所有来自 Napcat 的原始数据，然后无脑地把它们丢进公共的“中转站”（raw_event_queue）。
    它自己不做任何耗时的处理，永远保持畅通无阻！
    """
    global _adapter_instance
    if not _adapter_instance:
        logger.error("全局 Adapter 实例未设置，无法处理新连接！")
        return

    client_addr = websocket.remote_address
    logger.info(f"Napcat 客户端已连接: {client_addr}")
    _adapter_instance.connections.add(websocket)

    try:
        # 使用 async for 循环，优雅地处理每一条收到的消息
        async for raw_event_str in websocket:
            # 接待员现在只做一件事：把收到的所有东西都丢进队列！
            # 这个操作非常快，几乎不会阻塞
            await raw_event_queue.put(raw_event_str)
            logger.debug(
                f"已接收来自 {client_addr} 的原始数据: {raw_event_str[:100]}..."
            )  # 只打印前100个字符，避免日志过长

    except websockets.ConnectionClosed:
        logger.warning(f"Napcat 客户端 {client_addr} 连接已断开。")
    except Exception as e:
        logger.error(f"处理 Napcat 客户端 {client_addr} 时出错: {e}", exc_info=True)
    finally:
        # 无论如何，当连接结束时，一定要把它从我们的连接池里移除
        if _adapter_instance:
            _adapter_instance.connections.remove(websocket)
        logger.info(f"与 Napcat 客户端 {client_addr} 的会话结束。")


class NapcatAdapter(Adapter):
    """Napcat 适配器，DaY-Core 与 Napcat 世界沟通的唯一神使.

    它负责：
    - 启动一个 WebSocket 服务器，等待 Napcat 连接。
    - 将 Napcat 的原始事件，净化并认知成 DaY-Core 的标准事件对象。
    - 提供统一的 call_api 方法，将我们的指令（神权）传达给 Napcat。
    """

    def __init__(self, bot_instance: "Bot") -> None:
        global _adapter_instance
        self.bot = bot_instance
        # 从 bot 的 config 对象中读取配置，不再硬编码
        self.host = self.bot.config.adapter_host
        self.port = self.bot.config.adapter_port
        self._server_task: asyncio.Task | None = None
        # 使用集合来存储所有活跃的 Napcat 连接
        self.connections: set[websockets.WebSocketServerProtocol] = set()
        _adapter_instance = self

    def _convert_to_day_event(self, raw_event: dict[str, Any]) -> BaseEvent | None:
        """事件认知核心：将 Napcat 的原始 JSON 字典，转换为我们纯洁的 DaY-Core Event 对象."""
        post_type = raw_event.get("post_type")

        common_event_data = {
            "self_id": str(raw_event.get("self_id")),
            "time": int(raw_event.get("time", time.time())),
        }

        if post_type == "message":
            message_type = raw_event.get("message_type")
            common_data = {
                "self_id": str(raw_event.get("self_id")),
                "sub_type": raw_event.get("sub_type", ""),
                "message_id": str(raw_event.get("message_id")),
                "message": self._parse_message_segments(raw_event.get("message", [])),
                "raw_message": raw_event.get("raw_message", ""),
                "user_id": str(raw_event.get("user_id")),
                "sender": raw_event.get("sender"),  # sender 包含了发送者的详细信息
                "time": int(raw_event.get("time", time.time())),
            }
            # 根据具体消息类型，实例化不同的 Event 类
            if message_type == "private":
                return PrivateMessageEvent(**common_data)
            elif message_type == "group":
                return GroupMessageEvent(group_id=str(raw_event.get("group_id")), **common_data)

            message_type = raw_event.get("message_type")
            common_data = {
                **common_event_data,  # <-- 合并通用数据
                "sub_type": raw_event.get("sub_type", ""),
                "message_id": str(raw_event.get("message_id")),
                "message": self._parse_message_segments(raw_event.get("message", [])),
                "raw_message": raw_event.get("raw_message", ""),
                "user_id": str(raw_event.get("user_id")),
                "sender": raw_event.get("sender"),
            }
            if message_type == "private":
                return PrivateMessageEvent(**common_data)
            elif message_type == "group":
                return GroupMessageEvent(group_id=str(raw_event.get("group_id")), **common_data)

        elif post_type == "notice":
            notice_type = raw_event.get("notice_type")
            sub_type = raw_event.get("sub_type", "")

            # 群成员增加
            if notice_type == "group_increase":
                return GroupMemberIncreaseNoticeEvent(
                    **common_event_data,
                    group_id=str(raw_event.get("group_id")),
                    user_id=str(raw_event.get("user_id")),
                    operator_id=str(raw_event.get("operator_id")),
                )
            # 群成员减少
            elif notice_type == "group_decrease":
                return GroupMemberDecreaseNoticeEvent(
                    **common_event_data,
                    group_id=str(raw_event.get("group_id")),
                    user_id=str(raw_event.get("user_id")),
                    operator_id=str(raw_event.get("operator_id")),
                    sub_type=sub_type,
                )
            # 戳一戳 (notify->poke)
            elif notice_type == "notify" and sub_type == "poke":
                return GroupPokeNoticeEvent(
                    **common_event_data,
                    sub_type=sub_type,
                    group_id=str(raw_event.get("group_id")),
                    user_id=str(raw_event.get("user_id")),
                    target_id=str(raw_event.get("target_id")),
                )
            # 在这里可以继续添加对其他 notice_type 的解析...
            # 如果是未知的 notice 类型，就先返回一个基础的 NoticeEvent
            else:
                return NoticeEvent(**common_event_data, notice_type=notice_type)

        elif post_type == "request":
            request_type = raw_event.get("request_type")
            common_request_data = {
                **common_event_data,
                "flag": raw_event.get("flag", ""),
                "user_id": str(raw_event.get("user_id")),
                "comment": raw_event.get("comment", ""),
            }
            # 好友请求
            if request_type == "friend":
                return FriendAddRequestEvent(**common_request_data)
            # 加群请求
            elif request_type == "group":
                return GroupAddRequestEvent(
                    **common_request_data,
                    sub_type=raw_event.get("sub_type", ""),
                    group_id=str(raw_event.get("group_id")),
                )
            # 未知的 request 类型
            else:
                return RequestEvent(**common_event_data, request_type=request_type)

        return None

    def _parse_message_segments(self, napcat_segments: list) -> Message:
        """消息解析：将 Napcat 的消息段数组，转换为我们自己的 Message 对象."""
        day_segments = []
        for seg_data in napcat_segments:
            seg_type = seg_data.get("type", "unknown")
            data = seg_data.get("data", {})
            day_segments.append(MessageSegment(type=seg_type, data=data))
        return Message(day_segments)

    async def call_api(self, action: str, params: dict[str, Any]) -> Any:
        """神权代行核心：统一的 API 调用方法.

        它会发送请求，并异步等待响应，不会阻塞事件处理。

        Args:
            action (str): 要调用的 Napcat action 名称。
            params (Dict[str, Any]): action 所需的参数。

        Returns:
            Any: 成功时返回 API 响应的 "data" 字段，可能为 None 或任何类型。
                 失败时返回特殊的 API_FAILED 对象。
        """
        if not self.connections:
            logger.error(f"API 调用失败 ({action}): 没有可用的 Napcat 连接。")
            return API_FAILED

        # 从连接池中随便拿一个可用的连接来发送 API 请求
        conn = next(iter(self.connections))
        echo = f"day-core-api-{time.time_ns()}"
        payload = {"action": action, "params": params, "echo": echo}

        try:
            await conn.send(json.dumps(payload))
            # 发送后，我们使用 api.py 中的工具虔诚地等待响应
            response = await wait_for_response(echo)

            if response and response.get("status") == "ok":
                logger.debug(f"API '{action}' 调用成功, data: {response.get('data')}")
                return response.get("data")
            else:
                err_msg = (
                    response.get("wording") or response.get("message", "未知错误")
                    if response
                    else "无响应"
                )
                retcode = response.get("retcode", "N/A") if response else "N/A"
                logger.warning(f"API '{action}' 调用失败: {err_msg} (retcode: {retcode})")
                return API_FAILED
        except Exception as e:
            logger.error(f"API 调用 ({action}) 过程中发生异常: {e}", exc_info=True)
            return API_FAILED

    async def send_message(
        self, conversation_id: str, message_type: str, message: Message | MessageSegment
    ) -> dict[str, Any] | None:
        """发送消息的具体实现，它会调用通用的 call_api 方法."""
        # 1. 检查传入的 message 是不是 MessageSegment 的实例
        if isinstance(message, MessageSegment):
            # 如果是，就把它放进一个列表里，变成一个 Message 对象
            message = Message([message])

        logger.info(f"准备向 {message_type}:{conversation_id} 发送消息: {message.get_plain_text()}")

        napcat_segs = [{"type": seg.type, "data": seg.data} for seg in message]

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

        return await self.call_api(action, params)

    async def set_group_kick(
        self, group_id: str, user_id: str, reject_add_request: bool = False
    ) -> Any:  # <-- 返回值改为 Any，因为 call_api 的返回值就是 Any
        """踢出群成员."""
        logger.info(f"API CALL: set_group_kick(group_id={group_id}, user_id={user_id})")
        return await self.call_api(
            "set_group_kick",
            {
                "group_id": int(group_id),
                "user_id": int(user_id),
                "reject_add_request": reject_add_request,
            },
        )

    async def set_friend_add_request(self, flag: str, approve: bool, remark: str = "") -> Any:
        """处理加好友请求.

        Args:
            flag (str): 请求的 flag 标识.
            approve (bool): True 表示同意, False 表示拒绝.
            remark (str): 同意后的好友备注.
        """
        logger.info(f"API CALL: set_friend_add_request(flag={flag}, approve={approve})")
        return await self.call_api(
            "set_friend_add_request",
            {"flag": flag, "approve": approve, "remark": remark},
        )

    async def set_group_add_request(
        self, flag: str, sub_type: str, approve: bool, reason: str = ""
    ) -> Any:
        """处理加群请求／邀请.

        Args:
            flag (str): 请求的 flag 标识.
            sub_type (str): 'add' (申请) 或 'invite' (邀请).
            approve (bool): True 表示同意, False 表示拒绝.
            reason (str): 拒绝时的理由.
        """
        logger.info(f"API CALL: set_group_add_request(flag={flag}, approve={approve})")
        # 文档里写着 sub_type 或 type，为了兼容，我们传 type
        return await self.call_api(
            "set_group_add_request",
            {"flag": flag, "type": sub_type, "approve": approve, "reason": reason},
        )

    # 在这里可以继续添加更多 API 的封装，比如 ban_member, get_group_list 等等

    async def run(self) -> None:
        """启动 Adapter，也就是启动 WebSocket 服务器."""
        logger.info("Napcat 使徒 (服务器模式) 已准备就绪，开门迎客！")
        # websockets.serve 会启动一个服务器，并为每一个新的连接调用 global_ws_handler
        server = await websockets.serve(global_ws_handler, self.host, self.port)
        logger.info(f"DaY-Core (作为服务器) 正在启动，监听地址 ws://{self.host}:{self.port}")

        # 这是一个优雅的技巧，让服务器永远运行，直到被外部取消
        async def server_shutdown_wrapper() -> None:
            try:
                await asyncio.Future()
            finally:
                logger.info("服务器正在关闭所有连接...")
                server.close()
                await server.wait_closed()

        self._server_task = asyncio.create_task(server_shutdown_wrapper())

    async def stop(self) -> None:
        """停止 Adapter，也就是关闭 WebSocket 服务器."""
        logger.info("Napcat 使徒 (服务器模式) 正在关门谢客...")
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            # --- 核心修复点在这里！ ---
            # 使用 suppress 来优雅地忽略 CancelledError
            with suppress(asyncio.CancelledError):
                await self._server_task
        logger.info("服务器任务已停止。")
