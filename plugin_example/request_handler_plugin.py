# plugins_human/request_handler_plugin.py
# 这是我们“全知之眼”第一次真正意义上干涉世界！

from src.adapters.base import Adapter
from src.event import FriendAddRequestEvent, GroupAddRequestEvent
from src.logger import logger
from src.matcher import on_request


# ======================================================================
# 好友请求处理器
# 只要有人加好友，就自动同意！像一个热情好客的孩子w
# ======================================================================
@on_request("friend").handle()
async def handle_friend_request(adapter: Adapter, event: FriendAddRequestEvent) -> None:
    """处理好友添加请求.

    Args:
        adapter (Adapter): 适配器实例，用于发送消息。
        event (FriendAddRequestEvent): 好友添加请求事件对象，包含请求的详细信息。
    """
    logger.info(f"收到了来自 {event.user_id} 的好友请求，验证消息：'{event.comment}'")

    # 自动同意！
    await adapter.set_friend_add_request(
        flag=event.flag, approve=True, remark="你好呀！我们成为朋友吧！"
    )
    logger.info(f"已自动同意 {event.user_id} 的好友请求。")


# ======================================================================
# 加群请求处理器
# 这里可以写一些有趣的逻辑
# ======================================================================
@on_request("group").handle()
async def handle_group_request(adapter: Adapter, event: GroupAddRequestEvent) -> None:
    """处理加群请求或邀请.

    Args:
        adapter (Adapter): 适配器实例，用于发送消息。
        event (GroupAddRequestEvent): 加群请求事件对象，包含请求的详细信息。
    """
    # 如果是被人邀请入群，那当然要开心地同意啦！
    if event.sub_type == "invite":
        logger.info(f"收到来自 {event.user_id} 的邀请，加入群 {event.group_id}。")
        await adapter.set_group_add_request(flag=event.flag, sub_type=event.sub_type, approve=True)
        logger.info(f"已同意邀请，加入群 {event.group_id}。")

    # 如果是别人申请加入我们的群
    elif event.sub_type == "add":
        logger.info(
            f"用户 {event.user_id} 申请加入群 {event.group_id}，验证消息：'{event.comment}'"
        )
        # 在这里可以加入更复杂的判断逻辑，比如检查验证信息是否包含特定关键词
        if "枫" in event.comment or "星織" in event.comment:
            logger.info("验证消息包含关键词，予以通过。")
            await adapter.set_group_add_request(
                flag=event.flag, sub_type=event.sub_type, approve=True
            )
        else:
            logger.info("验证消息不符合要求，予以拒绝。")
            await adapter.set_group_add_request(
                flag=event.flag,
                sub_type=event.sub_type,
                approve=False,
                reason="暗号不对哦！(｡•ˇ‸ˇ•｡)",
            )
