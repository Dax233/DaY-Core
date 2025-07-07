# src/message.py
from collections.abc import Iterable
from typing import Any


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


class Message(list):
    """消息.

    一个 MessageSegment 的列表，代表一条完整的消息。
    提供了方便的链式操作和内容提取方法。
    """

    def __init__(self, segments: Iterable[MessageSegment] = ()) -> None:
        super().__init__(segments)

    def get_plain_text(self) -> str:
        """提取消息中的所有纯文本内容.

        Returns:
            str: 拼接后的纯文本字符串。
        """
        return "".join(str(seg.data.get("text", "")) for seg in self if seg.type == "text")

    @staticmethod
    def text(content: str) -> "MessageSegment":
        """创建一个纯文本消息段.

        Args:
            content (str): 文本内容。

        Returns:
            MessageSegment: 一个类型为 'text' 的消息段。
        """
        return MessageSegment("text", {"text": content})

    @staticmethod
    def image(file: str) -> "MessageSegment":
        r"""创建一个图片消息段.

        Args:
            file (str): 图片的来源。
                可以是本地路径 (e.g., 'C:\pics\1.jpg'),
                网络 URL (e.g., 'http://.../1.png'),
                或是 Base64 编码 (e.g., 'base64://...').

        Returns:
            MessageSegment: 一个类型为 'image' 的消息段。
        """
        return MessageSegment("image", {"file": file})

    # ... 以后可以添加更多的工厂方法，比如 at, face 等 ...
