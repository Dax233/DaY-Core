# plugins_human/test_features.py
import re
from src.logger import logger
from src.matcher import on_command, on_keyword, on_regex
from src.adapters.base import Adapter
from src.event import GroupMessageEvent
from src.message import Message, MessageSegment

# --- 测试 on_keyword ---
@on_keyword({"你好", "hello"}).handle()
async def handle_greeting(adapter: Adapter, event: GroupMessageEvent):
    # 注意：这里我们特意指定了 GroupMessageEvent，
    # 这样私聊时就不会触发了，而且还能直接用 event.group_id
    logger.info("关键词 '你好' 被触发！")
    reply = Message([MessageSegment("text", {"text": "你好呀！(｡･ω･｡)ﾉ"})])
    await adapter.send_message(event.group_id, "group", reply)


# --- 测试 on_regex 和依赖注入 ---
# 匹配 "echo [任何内容]"
@on_regex(r"^echo\s+(.*)").handle()
async def handle_echo(adapter: Adapter, event: GroupMessageEvent, matched: re.Match):
    # 看！我们直接拿到了 re.Match 对象！
    echo_content = matched.group(1).strip()
    logger.info(f"正则 'echo' 被触发，内容: {echo_content}")

    # 直接把用户说的内容原样发回去
    reply = Message([MessageSegment("text", {"text": echo_content})])
    await adapter.send_message(event.group_id, "group", reply)

# --- 测试依赖注入 Message 对象 ---
@on_command("分析消息").handle()
async def analyze_message(adapter: Adapter, event: GroupMessageEvent, msg: Message):
    # 看！我们直接拿到了 Message 对象，而不需要 event.message
    logger.info("命令 '分析消息' 被触发！")
    
    text_content = msg.get_plain_text()
    image_count = sum(1 for seg in msg if seg.type == "image")
    
    analysis_result = f"消息分析结果：\n纯文本内容: {text_content}\n图片数量: {image_count}"
    
    reply = Message([MessageSegment("text", {"text": analysis_result})])
    await adapter.send_message(event.group_id, "group", reply)