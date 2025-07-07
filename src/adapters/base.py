# src/adapters/base.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from ..message import Message, MessageSegment

if TYPE_CHECKING:
    from ..bot import Bot

class Adapter(ABC):
    def __init__(self, bot: "Bot"):
        self.bot = bot

    @abstractmethod
    async def run(self):
        """启动 Adapter。"""
        raise NotImplementedError

    @abstractmethod
    async def stop(self):
        """停止 Adapter。"""
        raise NotImplementedError

    @abstractmethod
    async def send_message(self, conversation_id: str, message_type: str, message: Message | MessageSegment) -> Any:
        """发送消息的抽象方法，可以接受 Message 或单个 MessageSegment。"""
        raise NotImplementedError