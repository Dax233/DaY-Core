# src/event.py
import time
from dataclasses import dataclass, field
from typing import Any

from .message import Message


@dataclass
class BaseEvent:
    """事件的基类."""

    time: int = field(default_factory=lambda: int(time.time()))
    self_id: str = ""
    post_type: str = ""


@dataclass
class MessageEvent(BaseEvent):
    """消息事件的基类."""

    post_type: str = "message"
    message_type: str = ""
    sub_type: str = ""
    message_id: str = ""
    message: Message = field(default_factory=Message)
    raw_message: str = ""
    user_id: str = ""
    sender: dict[str, Any] | None = None  # <--- 在这里加上 sender 字段！

    def get_user_id(self) -> str:
        """获取用户 ID."""
        return self.user_id


@dataclass
class PrivateMessageEvent(MessageEvent):
    """私聊消息事件."""

    message_type: str = "private"


@dataclass
class GroupMessageEvent(MessageEvent):
    """群消息事件."""

    message_type: str = "group"
    group_id: str = ""


@dataclass
class NoticeEvent(BaseEvent):
    """通知事件的基类."""

    post_type: str = "notice"
    notice_type: str = ""


@dataclass
class GroupMemberIncreaseNoticeEvent(NoticeEvent):
    """群成员增加事件.

    Attributes:
        notice_type (str): "group_increase"
        group_id (str): 群号
        user_id (str): 新成员的 QQ 号
        operator_id (str): 操作者的 QQ 号 (邀请者或管理员)
    """

    notice_type: str = "group_increase"
    group_id: str = ""
    user_id: str = ""
    operator_id: str = ""


@dataclass
class GroupMemberDecreaseNoticeEvent(NoticeEvent):
    """群成员减少事件.

    Attributes:
        notice_type (str): "group_decrease"
        group_id (str): 群号
        user_id (str): 离开成员的 QQ 号
        operator_id (str): 操作者的 QQ 号 (如果是被踢)
        sub_type (str): "leave" (主动退群), "kick" (被踢), "kick_me" (机器人自己被踢)
    """

    notice_type: str = "group_decrease"
    group_id: str = ""
    user_id: str = ""
    operator_id: str = ""
    sub_type: str = ""


@dataclass
class GroupPokeNoticeEvent(NoticeEvent):
    """群内戳一戳事件.

    Attributes:
        notice_type (str): "notify"
        sub_type (str): "poke"
        group_id (str): 群号
        user_id (str): 发起戳一戳的成员 QQ 号
        target_id (str): 被戳的成员 QQ 号 (可能是我自己！)
    """

    notice_type: str = "notify"
    sub_type: str = "poke"
    group_id: str = ""
    user_id: str = ""
    target_id: str = ""


@dataclass
class RequestEvent(BaseEvent):
    """请求事件的基类."""

    post_type: str = "request"
    request_type: str = ""
    flag: str = ""  # 这是同意/拒绝请求的关键凭证！一定要保存好！


@dataclass
class FriendAddRequestEvent(RequestEvent):
    """好友添加请求."""

    request_type: str = "friend"
    user_id: str = ""
    comment: str = ""  # 验证信息


@dataclass
class GroupAddRequestEvent(RequestEvent):
    """加群请求/邀请."""

    request_type: str = "group"
    sub_type: str = ""  # "add" (申请加群), "invite" (被邀请入群)
    group_id: str = ""
    user_id: str = ""
    comment: str = ""  # 验证信息


@dataclass
class MetaEvent(BaseEvent):
    """元事件的基类."""

    post_type: str = "meta_event"
    meta_event_type: str = ""


@dataclass
class LifecycleEvent(MetaEvent):
    """生命周期事件."""

    meta_event_type: str = "lifecycle"
    sub_type: str = ""  # "connect", "enable", "disable"


@dataclass
class HeartbeatEvent(MetaEvent):
    """心跳事件."""

    meta_event_type: str = "heartbeat"
    status: Any = None
    interval: int = 0
