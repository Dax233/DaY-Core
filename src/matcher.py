# src/matcher.py
import inspect
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar

from .event import BaseEvent, MessageEvent, NoticeEvent, RequestEvent
from .logger import logger
from .message import Message

# --- 这就是打破循环导入的魔法！ ---
if TYPE_CHECKING:
    from .adapters.base import Adapter
    from .bot import Bot

Handler = Callable[..., Any]
_startup_hooks: list[Callable] = []
_shutdown_hooks: list[Callable] = []


class Matcher:
    """事件响应器，我们框架的绝对核心."""

    instances: ClassVar[list["Matcher"]] = []

    def __init__(self, rule: Callable[[BaseEvent], bool], priority: int = 10) -> None:
        self.rule = rule
        self.priority = priority
        self.handlers: list[Handler] = []
        Matcher.instances.append(self)
        Matcher.instances.sort(key=lambda m: m.priority)

    def handle(self) -> Callable[[Handler], Handler]:
        """装饰器，用于注册处理函数."""

        def decorator(func: Handler) -> Handler:
            self.handlers.append(func)
            return func

        return decorator

    @classmethod
    async def run_all(cls, bot: "Bot", adapter: "Adapter", event: BaseEvent) -> None:
        """依赖注入的最终形态!"""
        # 在函数内部导入，避免在模块加载时出现问题
        from .adapters.base import Adapter
        from .bot import Bot

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
                            elif inspect.isclass(param.annotation) and issubclass(
                                type(event), param.annotation
                            ):
                                injection_args[param_name] = event
                            elif param.annotation == Message:
                                if isinstance(event, MessageEvent):
                                    injection_args[param_name] = event.message
                            elif param.annotation == re.Match and isinstance(rule_result, re.Match):
                                injection_args[param_name] = rule_result

                        await handler(**injection_args)
            except Exception as e:
                logger.error(f"执行 Matcher 时出错: {e}", exc_info=True)


# --- 工厂函数保持不变 ---
def on_message(priority: int = 10) -> Matcher:
    """创建一个基于消息事件的 Matcher.

    Args:
        priority (int): 匹配器的优先级，数值越小优先级越高。
    Returns:
        Matcher: 返回一个 Matcher 实例。
    """

    def rule(event: BaseEvent) -> bool:
        return isinstance(event, MessageEvent)

    return Matcher(rule=rule, priority=priority)


def on_command(command: str, priority: int = 5) -> Matcher:
    """创建一个基于命令的 Matcher.

    Args:
        command (str): 命令字符串，通常以斜杠开头。
        priority (int): 匹配器的优先级，数值越小优先级越高。
    Returns:
        Matcher: 返回一个 Matcher 实例。
    """

    def rule(event: BaseEvent) -> bool:
        return isinstance(event, MessageEvent) and event.raw_message.strip().startswith(command)

    return Matcher(rule=rule, priority=priority)


def on_keyword(keywords: set[str], priority: int = 8) -> Matcher:
    """创建一个基于关键词的 Matcher.

    Args:
        keywords (set[str]): 关键词集合。
        priority (int): 匹配器的优先级，数值越小优先级越高。
    Returns:
        Matcher: 返回一个 Matcher 实例。
    """

    def rule(event: BaseEvent) -> bool:
        if not isinstance(event, MessageEvent):
            return False
        message_text = event.message.get_plain_text()
        return any(keyword in message_text for keyword in keywords)

    return Matcher(rule=rule, priority=priority)


def on_regex(pattern: str, priority: int = 9) -> Matcher:
    """创建一个基于正则表达式的 Matcher.

    Args:
        pattern (str): 正则表达式模式。
        priority (int): 匹配器的优先级，数值越小优先级越高。
    Returns:
        Matcher: 返回一个 Matcher 实例。
    """
    compiled_pattern = re.compile(pattern)

    def rule(event: BaseEvent) -> re.Match | bool:
        if not isinstance(event, MessageEvent):
            return False
        match = compiled_pattern.search(event.raw_message)
        return match or False

    return Matcher(rule=rule, priority=priority)


def on_notice(notice_type: str | None = None, priority: int = 10) -> Matcher:
    """创建一个匹配通知事件的 Matcher.

    Args:
        notice_type (str | None): 可选，指定要匹配的 notice_type，如 'group_increase'。
                                  如果为 None，则匹配所有通知事件。
        priority (int): 匹配器的优先级。
    Returns:
        Matcher: 返回一个 Matcher 实例。
    """

    def rule(event: BaseEvent) -> bool:
        # 基础规则：必须是 NoticeEvent
        if not isinstance(event, NoticeEvent):
            return False
        # 进阶规则：如果指定了 notice_type，就必须匹配！
        return not (notice_type is not None and event.notice_type != notice_type)

    # 所有规则都通过了
    return Matcher(rule=rule, priority=priority)


def on_request(request_type: str | None = None, priority: int = 10) -> Matcher:
    """创建一个匹配请求事件的 Matcher.

    Args:
        request_type (str | None): 可选，指定要匹配的 request_type，如 'friend' 或 'group'。
                                   如果为 None，则匹配所有请求事件。
        priority (int): 匹配器的优先级。
    Returns:
        Matcher: 返回一个 Matcher 实例。
    """

    def rule(event: BaseEvent) -> bool:
        # 基础规则：必须是 RequestEvent
        if not isinstance(event, RequestEvent):
            return False
        # 进阶规则：如果指定了 request_type，就必须匹配！
        return not (request_type is not None and event.request_type != request_type)

    # 所有规则都通过了
    return Matcher(rule=rule, priority=priority)


# --- 思考题：这里的实现还可以更酷！---
# 比如 on_notice("group_increase") 这样的写法，
# 可以在 rule 函数里判断 event.notice_type 是否等于 "group_increase"。
# 不过现在这样已经完全可用了，优化可以放在下一个版本！(ゝ∀･)


def on_startup(func: Callable) -> Callable:
    """注册一个启动时执行的函数.

    这是一个装饰器，它会将函数添加到一个全局列表中，供 Bot 在启动时调用.
    """
    _startup_hooks.append(func)
    return func


def on_shutdown(func: Callable) -> Callable:
    """注册一个关闭时执行的函数.

    这是一个装饰器，它会将函数添加到一个全局列表中，供 Bot 在关闭时调用.
    """
    _shutdown_hooks.append(func)
    return func
