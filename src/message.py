# src/message.py
from typing import List, Dict, Any, overload, Iterable

class MessageSegment:
    def __init__(self, type: str, data: Dict[str, Any]):
        self.type = type
        self.data = data

    def __str__(self):
        if self.type == "text":
            return self.data.get("text", "")
        return f"[CQ:{self.type},...]" # 简化表示

    def __repr__(self):
        return f"MessageSegment(type='{self.type}', data={self.data})"

class Message(list):
    def __init__(self, segments: Iterable[MessageSegment] = ()):
        super().__init__(segments)

    def get_plain_text(self) -> str:
        """提取消息中的所有纯文本。"""
        return "".join(str(seg.data.get("text", "")) for seg in self if seg.type == "text")

    @staticmethod
    def text(content: str) -> "MessageSegment":
        return MessageSegment("text", {"text": content})

    @staticmethod
    def image(file: str) -> "MessageSegment":
        # file 可以是路径, url, base64
        return MessageSegment("image", {"file": file})

    # ... 以后可以添加更多的工厂方法，比如 at, face 等 ...