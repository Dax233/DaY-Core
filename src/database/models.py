# src/database/models.py
import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

# 声明所有 ORM 模型的基类
Base = declarative_base()


class MessageRecord(Base):
    """消息记录模型，用于在数据库中存储每一条消息.

    Attributes:
        id (int): 消息记录的唯一标识符.
        time (datetime): 消息发送的时间戳.
        self_id (str): 发送消息的用户或机器人 ID.
        message_type (str): 消息类型，可能是 'group' 或 'private'.
        group_id (str): 如果是群消息，则为群 ID；如果是私聊消息，则为 None.
        user_id (str): 发送消息的用户 ID.
        sender_name (str): 发送者的名称或昵称.
        raw_message (str): 原始消息内容，可能包含文本、图片等多种类型的消息数据.
    """

    __tablename__ = "message_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime, nullable=False, default=datetime.datetime.now)
    self_id = Column(String, nullable=False)
    message_type = Column(String(20), nullable=False)  # 'group' or 'private'
    group_id = Column(String, nullable=True)  # 私聊时为 None
    user_id = Column(String, nullable=False)
    sender_name = Column(String, nullable=False)
    raw_message = Column(Text, nullable=False)

    def __repr__(self) -> str:
        """返回消息记录的字符串表示形式."""
        return (
            f"<MessageRecord(id={self.id}, user_id='{self.user_id}', group_id='{self.group_id}')>"
        )
