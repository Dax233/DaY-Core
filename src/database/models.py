# src/database/models.py
import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base

# 声明所有 ORM 模型的基类
Base = declarative_base()


class EventRecord(Base):
    """事件记录模型，用于在数据库中存储所有需要持久化的事件.

    Attributes:
        id (int): 事件记录的唯一标识符.
        time (datetime): 事件发生的时间戳，默认为当前时间.
        self_id (str): 事件来源的 ID，通常是 Bot 的 ID.
        post_type (str): 事件的类型，例如 'message', 'notice', 'request', 'meta_event'.
        event_type (str): 事件的具体类型，例如 'private', 'group_increase', 'friend' 等.
        sub_type (str): 事件的子类型，可选字段，具体取决于 event_type 的值.
        group_id (str): 关联的群 ID，如果事件与群相关.
        user_id (str): 关联的用户 ID，如果事件与用户相关.
        summary (str): 事件的摘要信息，用于快速识别事件内容.
        details (str): 事件的详细数据，以 JSON 格式存储，包含所有相关信息.
    """

    __tablename__ = "event_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime, nullable=False, default=datetime.datetime.now)
    self_id = Column(String, nullable=False)
    post_type = Column(String(20), nullable=False)  # 'message', 'notice', 'request', 'meta_event'

    # 为了通用性，我们将具体类型和子类型也记录下来
    event_type = Column(String(30), nullable=False)  # e.g., 'private', 'group_increase', 'friend'
    sub_type = Column(String(30), nullable=True)

    # 关联 ID，让查询更方便
    group_id = Column(String, nullable=True)
    user_id = Column(String, nullable=True)

    # 为了能直观地看懂日志，我们加一个摘要字段
    summary = Column(Text, nullable=False)
    # 完整的事件数据，以 JSON 格式存储
    details = Column(Text, nullable=False)

    def __repr__(self) -> str:
        """返回事件记录的字符串表示."""
        return (
            f"<EventRecord(id={self.id}, "
            f"post_type='{self.post_type}', "
            f"event_type='{self.event_type}')>"
        )
