# plugins_human/admin_plugin.py
import re

from src.adapters.base import Adapter
from src.api import API_FAILED
from src.event import GroupMessageEvent
from src.logger import logger
from src.matcher import on_command
from src.message import Message


@on_command("/kick ").handle()  # 注意命令后面加了个空格，避免误触
async def handle_kick(adapter: Adapter, event: GroupMessageEvent) -> None:
    """处理 /kick 命令，踢出指定的群成员.

    Args:
        adapter (Adapter): 适配器实例，用于发送消息。
        event (GroupMessageEvent): 群消息事件对象，包含触发此事件的群信息。
    """
    # 简单的权限检查
    sender_role = event.sender.get("role") if event.sender else "member"
    if sender_role not in {"owner", "admin"}:
        await adapter.send_message(event.group_id, "group", Message.text("你没有权限哦！"))
        return

    # 从消息中解析出要踢的人
    match = re.search(r"\[CQ:at,qq=(\d+)\]", event.raw_message)
    if not match:
        await adapter.send_message(event.group_id, "group", Message.text("请 @ 你要踢的人。"))
        return

    user_to_kick = match.group(1)

    # 不能踢自己或者机器人
    if user_to_kick == event.user_id:
        await adapter.send_message(event.group_id, "group", Message.text("你不能踢自己呀！"))
        return
    if user_to_kick == event.self_id:
        await adapter.send_message(event.group_id, "group", Message.text("我才不要踢我自己呢！"))
        return

    logger.info(f"准备在群 {event.group_id} 中踢出成员 {user_to_kick}...")

    # 行使神权！
    result = await adapter.kick_member(event.group_id, user_to_kick)

    # --- 核心修复点在这里！ ---
    # 我们判断 result 是不是那个特殊的失败信号对象
    if result is not API_FAILED:
        # 只要不是失败信号，就都算成功！
        # 无论 result 是 None, {}, 还是其他数据
        await adapter.send_message(
            event.group_id, "group", Message.text(f"已将用户 {user_to_kick} 移出本群。")
        )
    else:
        # 只有当 result 确确实实是 API_FAILED 时，才算失败
        await adapter.send_message(
            event.group_id,
            "group",
            Message.text("操作失败，可能是我没有权限，或者发生了未知错误。"),
        )
