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

    def node(self, uin: str, name: str, content: "Message | MessageSegment | str") -> Self:
        """追加一个合并转发节点 (node).

        **警告**: 此方法遵循 Napcat/LLOneBot 的实现，而非 go-cqhttp 标准。

        Args:
            uin (str): 节点中显示的用户 QQ 号 (在 Napcat 中称为 uin).
            name (str): 节点中显示的用户昵称 (在 Napcat 中称为 name).
            content (Message | MessageSegment | str): 该节点具体的消息内容.

        Returns:
            Self: 返回自身，以支持链式调用.
        """
        node_data = {
            "uin": str(uin),
            "name": name,
            # 这里的 content 可以直接是一个 MessageSegment 对象，或者字符串
            # 我们将它转换为 Napcat 期望的格式
            "content": [],
        }

        if isinstance(content, str):
            node_data["content"] = [MessageSegment("text", {"text": content}).__dict__]
        elif isinstance(content, MessageSegment):
            # 直接使用 MessageSegment 的字典表示
            node_data["content"] = [content.__dict__]
        elif isinstance(content, Message):
            node_data["content"] = [seg.__dict__ for seg in content]

        # 最终提交给API的content需要是消息段的字典列表
        final_content = []
        for seg_dict in node_data["content"]:
            final_content.append({"type": seg_dict["type"], "data": seg_dict["data"]})
        node_data["content"] = final_content

        # 注意！这里的 data 字段直接就是 node_data，而不是再包一层
        self.append(MessageSegment("node", node_data))
        return self

    def face(self, face_id: str | int) -> Self:
        """追加一个 QQ 原生表情.

        Args:
            face_id (str | int): QQ 表情的 ID.

        Returns:
            Self: 返回自身，以支持链式调用.
        """
        self.append(MessageSegment("face", {"id": str(face_id)}))
        return self

    def record(self, file: str) -> Self:
        r"""追加一段语音.

        Args:
            file (str): 语音来源 (本地路径, URL, Base64).

        Returns:
            Self: 返回自身，以支持链式调用.
        """
        self.append(MessageSegment("record", {"file": file}))
        return self

    def video(self, file: str) -> Self:
        r"""追加一个视频.

        Args:
            file (str): 视频来源 (本地路径, URL, Base64).

        Returns:
            Self: 返回自身，以支持链式调用.
        """
        self.append(MessageSegment("video", {"file": file}))
        return self

    def music(self, music_type: str, music_id: str) -> Self:
        """追加一个音乐分享 (QQ音乐/网易云等).

        Args:
            music_type (str): 音乐平台类型, 'qq', '163', 'kugou' 等.
            music_id (str): 音乐的 ID.

        Returns:
            Self: 返回自身，以支持链式调用.
        """
        self.append(MessageSegment("music", {"type": music_type, "id": music_id}))
        return self

    def music_custom(self, url: str, audio: str, title: str, image: str | None = None) -> Self:
        """追加一个自定义的音乐分享卡片.

        Args:
            url (str): 点击卡片后跳转的链接.
            audio (str): 音频的 URL.
            title (str): 音乐标题.
            image (str | None, optional): 封面图片的 URL. Defaults to None.

        Returns:
            Self: 返回自身，以支持链式调用.
        """
        data = {"type": "custom", "url": url, "audio": audio, "title": title}
        if image:
            data["image"] = image
        self.append(MessageSegment("music", data))
        return self
