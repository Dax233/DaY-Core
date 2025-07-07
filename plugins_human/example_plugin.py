# plugins_human/example_plugin.py
from src.logger import logger
from src.matcher import on_command
from src.adapters.base import Adapter
from src.event import MessageEvent
from src.message import Message
from src.bot import Bot

# 创建一个响应 "ping" 命令的 matcher
ping_matcher = on_command("ping")

@ping_matcher.handle()
async def handle_ping(bot: "Bot", adapter: Adapter, event: MessageEvent):
    logger.info(f"插件收到了来自 {event.get_user_id()} 的 ping 命令！")
    
    # 构建回复消息
    reply_message = Message([
        Message.text("pong!")
    ])
    
    # 调用 adapter 发送回复
    await adapter.send_message(
        conversation_id=event.group_id if event.message_type == "group" else event.user_id,
        message_type=event.message_type,
        message=reply_message
    )