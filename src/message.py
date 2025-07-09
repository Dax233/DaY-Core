# src/message.py
from collections.abc import Iterable
from typing import Any, Self


class MessageSegment:
    """消息段.

    表示一条消息中的一个独立部分，例如一段文字、一张图片、一个@等。
    它是构成 Message 对象的基本单位。

    Attributes:
        type (str): 消息段的类型，如 'text', 'image'。
        data (Dict[str, Any]): 存放该消息段具体数据的字典。
    """

    def __init__(self, type: str, data: dict[str, Any]) -> None:
        self.type = type
        self.data = data

    def __str__(self) -> str:
        """返回消息段的字符串表示，主要用于消息内容的拼接."""
        if self.type == "text":
            return self.data.get("text", "")
        # 对于非文本消息段，返回一个简化的 CQ 码格式，方便预览
        return f"[CQ:{self.type},...]"

    def __repr__(self) -> str:
        """返回消息段的官方、明确的字符串表示，主要用于调试."""
        return f"MessageSegment(type='{self.type}', data={self.data})"


class Message(list[MessageSegment]):
    """消息.

    一个 MessageSegment 的列表，代表一条完整的消息。
    提供了方便的链式操作和内容提取方法。
    """

    def __init__(self, segments: Iterable[MessageSegment] = ()) -> None:
        super().__init__(segments)

    def __add__(self, other: "MessageSegment | Message") -> "Message":
        """拼接消息段或另一条消息，返回一个新的 Message 对象."""
        new_message = self.copy()  # 创建一个副本，不修改原对象
        if isinstance(other, MessageSegment):
            new_message.append(other)
        elif isinstance(other, Message):
            new_message.extend(other)
        else:
            # 如果尝试拼接不支持的类型，就抛出异常
            return NotImplemented
        return new_message

    def __iadd__(self, other: "MessageSegment | Message") -> Self:
        """原地拼接消息段或另一条消息，修改自身."""
        if isinstance(other, MessageSegment):
            self.append(other)
        elif isinstance(other, Message):
            self.extend(other)
        else:
            return NotImplemented
        return self  # 返回自身，以支持链式操作

    def get_plain_text(self) -> str:
        """提取消息中的所有纯文本内容.

        Returns:
            str: 拼接后的纯文本字符串。
        """
        return "".join(str(seg) for seg in self if seg.type == "text")

    def text(self, content: str) -> Self:
        """追加一段纯文本.

        Args:
            content (str): 文本内容.

        Returns:
            Self: 返回自身，以支持链式调用.
        """
        self.append(MessageSegment("text", {"text": content}))
        return self

    def at(self, user_id: str | int) -> Self:
        """追加一个 @某人 的消息段.

        Args:
            user_id (str | int): 要 @ 的用户QQ号，'all' 表示 @全体.

        Returns:
            Self: 返回自身，以支持链式调用.
        """
        self.append(MessageSegment("at", {"qq": str(user_id)}))
        return self

    def at_all(self) -> Self:
        """追加一个 @全体成员 的消息段."""
        return self.at("all")

    def image(self, file: str) -> Self:
        r"""追加一张图片.

        Args:
            file (str): 图片来源 (本地路径, URL, Base64).

        Returns:
            Self: 返回自身，以支持链式调用.
        """
        self.append(MessageSegment("image", {"file": file}))
        return self

    def reply(self, message_id: str | int) -> Self:
        """追加一个回复消息段，让整条消息成为对某条消息的回复.

        根据 OneBot v11 规范，这个段通常放在消息链的最前面.
        """
        # 为了最佳实践，我们把它插入到列表的开头
        self.insert(0, MessageSegment("reply", {"id": str(message_id)}))
        return self
