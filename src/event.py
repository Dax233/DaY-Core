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
