# src/event.py
import time
from typing import Optional
from dataclasses import dataclass, field
from .message import Message

@dataclass
class BaseEvent:
    time: int = field(default_factory=lambda: int(time.time()))
    self_id: str = "" # 机器人自己的 QQ 号
    post_type: str = ""

@dataclass
class MessageEvent(BaseEvent):
    post_type: str = "message"
    message_type: str = "" # "private" or "group"
    sub_type: str = ""
    message_id: str = ""
    message: Message = field(default_factory=Message)
    raw_message: str = ""
    user_id: str = ""
    # ... 更多通用字段 ...

    def get_user_id(self) -> str:
        return self.user_id

@dataclass
class PrivateMessageEvent(MessageEvent):
    message_type: str = "private"

@dataclass
class GroupMessageEvent(MessageEvent):
    message_type: str = "group"
    group_id: str = ""

# ... 以后可以添加 NoticeEvent, RequestEvent 等 ...