# plugins_human/info_plugin.py
# 这是我们洞察世界的“水晶球”！

from re import Match

from src.adapters.base import Adapter
from src.api import API_FAILED
from src.event import GroupMessageEvent
from src.logger import logger
from src.matcher import on_command, on_regex
from src.message import Message


@on_command("/groups").handle()
async def handle_get_groups(adapter: Adapter, event: GroupMessageEvent) -> None:
    """获取并回复机器人所在的群列表."""
    logger.info("命令 /groups 被触发，正在获取群列表...")
    group_list = await adapter.get_group_list()

    if group_list is API_FAILED or not isinstance(group_list, list):
        await adapter.send_message(event.group_id, "group", Message().text("获取群列表失败了 T_T"))
        return

    reply_text = "我所在的群聊有：\n"
    for group in group_list:
        reply_text += f"- {group.get('group_name', '未知群名')} ({group.get('group_id')})\n"

    # 为了防止消息太长，我们只取前一部分
    reply_text = reply_text[:1000] + "..." if len(reply_text) > 1000 else reply_text
    await adapter.send_message(event.group_id, "group", Message().text(reply_text))


@on_command("/members").handle()
async def handle_get_members(adapter: Adapter, event: GroupMessageEvent) -> None:
    """获取当前群的成员列表."""
    logger.info(f"命令 /members 在群 {event.group_id} 被触发，正在获取成员列表...")
    member_list = await adapter.get_group_member_list(event.group_id)

    if member_list is API_FAILED or not isinstance(member_list, list):
        await adapter.send_message(
            event.group_id, "group", Message().text("获取成员列表失败了 T_T")
        )
        return

    reply_text = f"本群 ({event.group_id}) 共有 {len(member_list)} 位成员：\n"
    # 只显示前20个，防止刷屏
    for member in member_list[:20]:
        display_name = member.get("card") or member.get("nickname", "未知昵称")
        reply_text += f"- {display_name} ({member.get('user_id')})\n"

    if len(member_list) > 20:
        reply_text += f"...等共 {len(member_list)} 人。"

    await adapter.send_message(event.group_id, "group", Message().text(reply_text))


# 使用正则来匹配 /info [@user] 或 /info [QQ号]
@on_regex(r"^\/info(?:\s+\[CQ:at,qq=(\d+)\]|\s+(\d+))?$").handle()
async def handle_get_info(adapter: Adapter, event: GroupMessageEvent, matched: Match) -> None:
    """获取指定用户的信息，如果未指定，则获取发送者自己的信息."""
    # matched.group(1) 是 @ 的 QQ, matched.group(2) 是直接输入的 QQ
    target_id = matched.group(1) or matched.group(2) or event.user_id

    logger.info(f"命令 /info 被触发，查询目标: {target_id}")

    # 尝试在当前群获取成员信息
    user_info = await adapter.get_group_member_info(event.group_id, target_id)

    # 如果在群里找不到（比如查的是群外好友或机器人自己），就尝试获取陌生人信息
    if user_info is API_FAILED:
        logger.info(f"在群 {event.group_id} 中未找到 {target_id}，尝试作为陌生人查询...")
        user_info = await adapter.get_stranger_info(target_id)

    if user_info is API_FAILED or not isinstance(user_info, dict):
        await adapter.send_message(
            event.group_id,
            "group",
            Message().at(event.user_id).text(f" 查询 {target_id} 的信息失败了..."),
        )
        return

    # --- 格式化回复，这部分代码是艺术！---
    nickname = user_info.get("nickname", "N/A")
    card = user_info.get("card", "")
    user_id = user_info.get("user_id", "N/A")
    sex = user_info.get("sex", "unknown")
    age = user_info.get("age", "N/A")
    role = user_info.get("role", "member")
    join_time = user_info.get("join_time", 0)

    reply = Message().at(event.user_id).text(f" 查询到 {user_id} 的信息：\n")
    reply.text(f"昵称: {nickname}\n")
    if card:
        reply.text(f"群名片: {card}\n")
    reply.text(f"性别: {sex}\n")
    reply.text(f"年龄: {age}\n")
    if "role" in user_info:  # 只有群成员信息里有 role
        reply.text(f"权限: {role}\n")
    if join_time:
        import datetime

        join_dt = datetime.datetime.fromtimestamp(join_time)
        reply.text(f"加群时间: {join_dt.strftime('%Y-%m-%d %H:%M:%S')}")

    await adapter.send_message(event.group_id, "group", reply)
