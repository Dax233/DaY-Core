# plugins_human/example_plugin.py
from src.adapters.base import Adapter
from src.event import MessageEvent
from src.logger import logger
from src.matcher import on_command
from src.message import Message

# 创建一个响应 "ping" 命令的 matcher
ping_matcher = on_command("ping")


@ping_matcher.handle()
async def handle_ping(adapter: Adapter, event: MessageEvent) -> None:
    """处理 ping 命令，回复 pong!.

    Args:
        bot (Bot): 机器人实例，用于获取相关信息。
        adapter (Adapter): 适配器实例，用于发送消息。
        event (MessageEvent): 消息事件对象，包含触发此事件的用户信息。
    """
    logger.info(f"插件收到了来自 {event.get_user_id()} 的 ping 命令！")

    # 构建回复消息
    reply_message = Message().reply(event.message_id).text("pong! (｡ゝω･)bﾞ")

    # 调用 adapter 发送回复
    await adapter.send_message(
        conversation_id=event.group_id if event.message_type == "group" else event.user_id,
        message_type=event.message_type,
        message=reply_message,
    )
