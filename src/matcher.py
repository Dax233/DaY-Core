# src/matcher.py
import re
import inspect
from typing import List, Callable, Any, Dict, Type, TYPE_CHECKING, Set

from .event import BaseEvent, MessageEvent
from .logger import logger
from .message import Message

# --- 这就是打破循环导入的魔法！ ---
if TYPE_CHECKING:
    from .bot import Bot
    from .adapters.base import Adapter

Handler = Callable[..., Any]

class Matcher:
    instances: List["Matcher"] = []

    def __init__(self, rule: Callable[[BaseEvent], bool], priority: int = 10):
        self.rule = rule
        self.priority = priority
        self.handlers: List[Handler] = []
        Matcher.instances.append(self)
        Matcher.instances.sort(key=lambda m: m.priority)

    def handle(self) -> Callable[[Handler], Handler]:
        def decorator(func: Handler) -> Handler:
            self.handlers.append(func)
            return func
        return decorator

    @classmethod
    async def run_all(cls, bot: "Bot", adapter: "Adapter", event: BaseEvent):
        """
        依赖注入的最终形态！
        """
        # 在函数内部导入，避免在模块加载时出现问题
        from .bot import Bot
        from .adapters.base import Adapter

        for matcher in cls.instances:
            try:
                rule_result = matcher.rule(event)
                if rule_result:
                    for handler in matcher.handlers:
                        handler_params = inspect.signature(handler).parameters
                        injection_args = {}

                        for param_name, param in handler_params.items():
                            # 关键修复：我们直接比较 param.annotation 和我们导入的类！
                            if param.annotation == Bot:
                                injection_args[param_name] = bot
                            elif param.annotation == Adapter:
                                injection_args[param_name] = adapter
                            # issubclass 可以判断一个实例是否是某个类或其子类的实例
                            # 对于类型注解，我们需要判断 event 的类是否是注解类的子类
                            elif inspect.isclass(param.annotation) and issubclass(type(event), param.annotation):
                                injection_args[param_name] = event
                            elif param.annotation == Message:
                                if isinstance(event, MessageEvent):
                                    injection_args[param_name] = event.message
                            elif param.annotation == re.Match:
                                if isinstance(rule_result, re.Match):
                                    injection_args[param_name] = rule_result

                        await handler(**injection_args)
            except Exception as e:
                logger.error(f"执行 Matcher 时出错: {e}", exc_info=True)


# --- 工厂函数保持不变 ---
def on_message(priority: int = 10) -> Matcher:
    def rule(event: BaseEvent) -> bool:
        return isinstance(event, MessageEvent)
    return Matcher(rule=rule, priority=priority)

def on_command(command: str, priority: int = 5) -> Matcher:
    def rule(event: BaseEvent) -> bool:
        return isinstance(event, MessageEvent) and event.raw_message.strip().startswith(command)
    return Matcher(rule=rule, priority=priority)

def on_keyword(keywords: Set[str], priority: int = 8) -> Matcher:
    def rule(event: BaseEvent) -> bool:
        if not isinstance(event, MessageEvent):
            return False
        message_text = event.message.get_plain_text()
        return any(keyword in message_text for keyword in keywords)
    return Matcher(rule=rule, priority=priority)

def on_regex(pattern: str, priority: int = 9) -> Matcher:
    compiled_pattern = re.compile(pattern)
    def rule(event: BaseEvent) -> re.Match | bool:
        if not isinstance(event, MessageEvent):
            return False
        match = compiled_pattern.search(event.raw_message)
        return match or False
    return Matcher(rule=rule, priority=priority)