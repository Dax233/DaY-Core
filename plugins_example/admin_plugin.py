# plugins_human/admin_plugin.py
import re
from re import Match

from src.adapters.base import Adapter
from src.api import API_FAILED
from src.event import GroupMessageEvent
from src.logger import logger
from src.matcher import on_command, on_regex
from src.message import Message


# --- 权限检查的辅助函数，避免重复代码，这是优雅的体现！ ---
async def check_admin_permission(adapter: Adapter, event: GroupMessageEvent) -> bool:
    """检查用户是否为管理员或群主."""
    sender_role = event.sender.get("role") if event.sender else "member"
    if sender_role not in {"owner", "admin"}:
        await adapter.send_message(
            event.group_id, "group", Message().at(event.user_id).text(" 你没有权限哦！")
        )
        return False
    return True


@on_command("/kick ").handle()  # 注意命令后面加了个空格，避免误触
async def handle_kick(adapter: Adapter, event: GroupMessageEvent) -> None:
    """处理 /kick 命令，踢出指定的群成员.

    Args:
        adapter (Adapter): 适配器实例，用于发送消息。
        event (GroupMessageEvent): 群消息事件对象，包含触发此事件的群信息。
    """
    # 简单的权限检查
    if not await check_admin_permission(adapter, event):
        return

    # 从消息中解析出要踢的人
    match = re.search(r"\[CQ:at,qq=(\d+)\]", event.raw_message)
    if not match:
        await adapter.send_message(event.group_id, "group", Message().text("请 @ 你要踢的人。"))
        return

    user_to_kick = match.group(1)

    # 不能踢自己或者机器人
    if user_to_kick == event.user_id:
        await adapter.send_message(event.group_id, "group", Message().text("你不能踢自己呀！"))
        return
    if user_to_kick == event.self_id:
        await adapter.send_message(event.group_id, "group", Message().text("我才不要踢我自己呢！"))
        return

    logger.info(f"准备在群 {event.group_id} 中踢出成员 {user_to_kick}...")

    # 行使神权！
    result = await adapter.set_group_kick(event.group_id, user_to_kick)

    # --- 核心修复点在这里！ ---
    # 我们判断 result 是不是那个特殊的失败信号对象
    if result is not API_FAILED:
        # 只要不是失败信号，就都算成功！
        # 无论 result 是 None, {}, 还是其他数据
        await adapter.send_message(
            event.group_id, "group", Message().text(f"已将用户 {user_to_kick} 移出本群。")
        )
    else:
        # 只有当 result 确确实实是 API_FAILED 时，才算失败
        await adapter.send_message(
            event.group_id,
            "group",
            Message().text("操作失败，可能是我没有权限，或者发生了未知错误。"),
        )


# --- 使用正则表达式来匹配更复杂的命令，比如 /ban @user 10m ---
# r"^\/ban\s+\[CQ:at,qq=(\d+)\](?:\s+(\d+)([mhd]?))?$"
# ^\/ban\s+              -> 匹配 /ban 和至少一个空格
# \[CQ:at,qq=(\d+)\]     -> 匹配并捕获 @ 的 QQ 号
# (?:\s+(\d+)([mhd]?))? -> 这是一个非捕获组 (?:...)，整个是可选的 (?)
#   \s+                  -> 匹配空格
#   (\d+)                -> 捕获时间数值
#   ([mhd]?)             -> 捕获时间单位 (m, h, d)，也是可选的
@on_regex(r"^\/ban\s+\[CQ:at,qq=(\d+)\](?:\s+(\d+)([mhd]?))?$").handle()
async def handle_ban(adapter: Adapter, event: GroupMessageEvent, matched: Match) -> None:
    """处理禁言命令，支持分钟(m)、小时(h)、天(d)单位.

    Args:
        adapter (Adapter): 适配器实例，用于发送消息。
        event (GroupMessageEvent): 群消息事件对象，包含触发此事件的群信息。
        matched (Match): 正则匹配结果对象，包含匹配的用户QQ和时间参数。
    """
    if not await check_admin_permission(adapter, event):
        return

    user_to_ban = matched.group(1)
    time_value_str = matched.group(2)
    time_unit = matched.group(3)

    duration_seconds = 1800  # 默认禁言30分钟

    if time_value_str:
        try:
            time_value = int(time_value_str)
            if time_unit == "h":
                duration_seconds = time_value * 3600
            elif time_unit == "d":
                duration_seconds = time_value * 86400
            else:  # 默认为分钟 m
                duration_seconds = time_value * 60
        except ValueError:
            await adapter.send_message(event.group_id, "group", Message().text("无效的时间数值。"))
            return

    # 检查一下别把自己或者机器人给禁言了
    if user_to_ban == event.user_id:
        await adapter.send_message(event.group_id, "group", Message().text("你不能禁言自己呀！"))
        return
    if user_to_ban == event.self_id:
        await adapter.send_message(
            event.group_id, "group", Message().text("我才不要禁言我自己呢！")
        )
        return

    logger.info(f"准备在群 {event.group_id} 中禁言成员 {user_to_ban} {duration_seconds} 秒...")
    result = await adapter.set_group_ban(event.group_id, user_to_ban, duration_seconds)

    if result is not API_FAILED:
        await adapter.send_message(
            event.group_id,
            "group",
            Message().text(f"已将用户 {user_to_ban} 禁言 {duration_seconds} 秒。"),
        )
    else:
        await adapter.send_message(
            event.group_id,
            "group",
            Message().text("操作失败，可能是我没有权限，或者发生了未知错误。"),
        )


@on_command("/unban ").handle()
async def handle_unban(adapter: Adapter, event: GroupMessageEvent) -> None:
    """处理解禁命令.

    Args:
        adapter (Adapter): 适配器实例，用于发送消息。
        event (GroupMessageEvent): 群消息事件对象，包含触发此事件的群信息。
    """
    if not await check_admin_permission(adapter, event):
        return

    match = re.search(r"\[CQ:at,qq=(\d+)\]", event.raw_message)
    if not match:
        await adapter.send_message(
            event.group_id, "group", Message().text("请 @ 你要解除禁言的人。")
        )
        return

    user_to_unban = match.group(1)

    logger.info(f"准备在群 {event.group_id} 中为成员 {user_to_unban} 解除禁言...")
    # 解除禁言就是把禁言时间设置为 0
    result = await adapter.set_group_ban(event.group_id, user_to_unban, 0)

    if result is not API_FAILED:
        await adapter.send_message(
            event.group_id, "group", Message().text(f"已为用户 {user_to_unban} 解除禁言。")
        )
    else:
        await adapter.send_message(
            event.group_id,
            "group",
            Message().text("操作失败，可能是我没有权限，或者发生了未知错误。"),
        )


@on_command("/banall").handle()
async def handle_ban_all(adapter: Adapter, event: GroupMessageEvent) -> None:
    """处理开启全员禁言命令.

    Args:
        adapter (Adapter): 适配器实例，用于发送消息。
        event (GroupMessageEvent): 群消息事件对象，包含触发此事件的群信息。
    """
    if not await check_admin_permission(adapter, event):
        return

    logger.info(f"准备在群 {event.group_id} 中开启全员禁言...")
    result = await adapter.set_group_whole_ban(event.group_id, enable=True)
    if result is not API_FAILED:
        await adapter.send_message(event.group_id, "group", Message().text("已开启全员禁言。"))
    else:
        await adapter.send_message(
            event.group_id,
            "group",
            Message().text("操作失败，可能是我没有权限。"),
        )


@on_command("/unbanall").handle()
async def handle_unban_all(adapter: Adapter, event: GroupMessageEvent) -> None:
    """处理关闭全员禁言命令.

    Args:
        adapter (Adapter): 适配器实例，用于发送消息。
        event (GroupMessageEvent): 群消息事件对象，包含触发此事件的群信息。
    """
    if not await check_admin_permission(adapter, event):
        return

    logger.info(f"准备在群 {event.group_id} 中关闭全员禁言...")
    result = await adapter.set_group_whole_ban(event.group_id, enable=False)
    if result is not API_FAILED:
        await adapter.send_message(event.group_id, "group", Message().text("已关闭全员禁言。"))
    else:
        await adapter.send_message(
            event.group_id,
            "group",
            Message().text("操作失败，可能是我没有权限。"),
        )
