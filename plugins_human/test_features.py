# plugins_human/test_features.py
import re

from src.adapters.base import Adapter
from src.event import GroupMessageEvent
from src.logger import logger
from src.matcher import on_command, on_keyword, on_regex
from src.message import Message, MessageSegment


# --- 测试 on_keyword ---
@on_keyword({"你好", "hello"}).handle()
async def handle_greeting(adapter: Adapter, event: GroupMessageEvent) -> None:
    """响应问候语，发送你好.

    Args:
        adapter (Adapter): 适配器实例，用于发送消息。
        event (GroupMessageEvent): 触发此事件的群消息事件。
    """
    logger.info("关键词 '你好' 被触发！")
    reply = Message([MessageSegment("text", {"text": "你好呀！(｡･ω･｡)ﾉ"})])
    await adapter.send_message(event.group_id, "group", reply)


# --- 测试 on_regex 和依赖注入 ---
@on_regex(r"^echo\s+(.*)").handle()
async def handle_echo(adapter: Adapter, event: GroupMessageEvent, matched: re.Match) -> None:
    """响应 echo 命令，复述后面的内容.

    Args:
        adapter (Adapter): 适配器实例。
        event (GroupMessageEvent): 群消息事件。
        matched (re.Match): 正则表达式匹配对象。
    """
    echo_content = matched.group(1).strip()
    logger.info(f"正则 'echo' 被触发，内容: {echo_content}")
    reply = Message([MessageSegment("text", {"text": echo_content})])
    await adapter.send_message(event.group_id, "group", reply)


# --- 核心修复点在这里！ ---
@on_command("分析消息").handle()
async def analyze_message(adapter: Adapter, event: GroupMessageEvent, msg: Message) -> None:
    """分析一条消息的构成并回复.

    Args:
        adapter (Adapter): 适配器实例。
        event (GroupMessageEvent): 群消息事件。
        msg (Message): 被分析的消息对象，由框架自动注入。
    """
    logger.info("命令 '分析消息' 被触发！")

    text_content = msg.get_plain_text()
    image_count = sum(1 for seg in msg if seg.type == "image")

    analysis_result = f"消息分析结果：\n纯文本内容: '{text_content}'\n图片数量: {image_count}"

    reply = Message([MessageSegment("text", {"text": analysis_result})])
    await adapter.send_message(event.group_id, "group", reply)
