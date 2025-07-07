# src/adapters/base.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from ..message import Message, MessageSegment

if TYPE_CHECKING:
    from ..bot import Bot


class Adapter(ABC):
    """适配器的基类，所有适配器都应该继承自它.

    适配器负责与外部系统（如聊天平台）进行交互，处理消息的发送和接收。
    """

    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    @abstractmethod
    async def run(self) -> None:
        """启动 Adapter."""
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        """停止 Adapter."""
        raise NotImplementedError

    @abstractmethod
    async def send_message(
        self, conversation_id: str, message_type: str, message: Message | MessageSegment
    ) -> Any:
        """发送消息的抽象方法，可以接受 Message 或单个 MessageSegment."""
        raise NotImplementedError
