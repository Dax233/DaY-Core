# src/matcher.py
from typing import List, Callable, Any, Dict, Type, TYPE_CHECKING
from .event import BaseEvent, MessageEvent
from .logger import logger

if TYPE_CHECKING:
    from .bot import Bot
    from .adapters.base import Adapter # 我们需要一个 Adapter 基类

# Matcher 的处理函数类型
Handler = Callable[..., Any]

class Matcher:
    """事件响应器，我们框架的绝对核心。"""
    # 使用列表存储所有已创建的 Matcher 实例
    instances: List["Matcher"] = []

    def __init__(self, rule: Callable[[BaseEvent], bool], priority: int = 10):
        self.rule = rule  # 匹配规则，一个返回布尔值的函数
        self.priority = priority
        self.handlers: List[Handler] = []
        # 在创建时自动将自己注册到全局列表中
        Matcher.instances.append(self)
        # 根据优先级排序，数字越小优先级越高
        Matcher.instances.sort(key=lambda m: m.priority)

    def handle(self) -> Callable[[Handler], Handler]:
        """装饰器，用于注册处理函数。"""
        def decorator(func: Handler) -> Handler:
            self.handlers.append(func)
            return func
        return decorator

    @classmethod
    async def run_all(cls, bot: "Bot", adapter: "Adapter", event: BaseEvent):
        """
        遍历所有 Matcher，如果事件匹配规则，则执行其所有 handler。
        """
        for matcher in cls.instances:
            try:
                if matcher.rule(event):
                    for handler in matcher.handlers:
                        # 在这里，我们神奇地把 bot, adapter, event 注入到 handler 里！
                        # 这就是“依赖注入”，非常高级的玩法！
                        await handler(bot=bot, adapter=adapter, event=event)
            except Exception as e:
                logger.error(f"执行 Matcher 时出错: {e}", exc_info=True)


# --- 工厂函数，让创建 Matcher 更简单、更语义化 ---

def on_message(priority: int = 10) -> Matcher:
    """响应所有消息事件的 Matcher。"""
    def rule(event: BaseEvent) -> bool:
        return isinstance(event, MessageEvent)
    return Matcher(rule=rule, priority=priority)

def on_command(command: str, priority: int = 5) -> Matcher:
    """响应特定命令的 Matcher。"""
    def rule(event: BaseEvent) -> bool:
        # 必须是消息事件，并且消息的纯文本以命令开头
        return isinstance(event, MessageEvent) and event.raw_message.strip().startswith(command)
    return Matcher(rule=rule, priority=priority)