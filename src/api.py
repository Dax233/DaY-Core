# src/api.py
import asyncio
import time
from typing import Dict, Any, Optional

from .logger import logger

# 这个字典用来存放我们所有待处理的“祈祷”
# key 是请求的 echo ID，value 是一个 asyncio.Future 对象，代表着对“神谕”的期待
_pending_futures: Dict[str, asyncio.Future] = {}

class APICallFailed:
    pass

API_FAILED = APICallFailed()

async def wait_for_response(echo: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
    """
    等待一个特定 echo 的 API 响应。
    """
    future = asyncio.Future()
    _pending_futures[echo] = future
    try:
        logger.debug(f"正在等待 API 响应 (echo: {echo}, 超时: {timeout}s)...")
        # 我们会在这里一直等待，直到 future 被设置结果，或者超时
        result = await asyncio.wait_for(future, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"等待 API 响应超时 (echo: {echo})")
        return None
    finally:
        # 无论成功还是失败，都要把这个“祈祷”从等待列表中移除
        _pending_futures.pop(echo, None)

def resolve_response(response: Dict[str, Any]):
    """
    当收到 Napcat 的响应时，调用此函数来回应我们的“祈祷”。
    """
    echo = response.get("echo")
    if not echo:
        return

    future = _pending_futures.get(str(echo))
    if future and not future.done():
        # 找到了对应的“祈祷”，把“神谕”告诉它！
        future.set_result(response)
        logger.debug(f"已匹配并处理 API 响应 (echo: {echo})")
    else:
        # 可能是超时后才收到的响应，或者是一个我们不认识的 echo
        logger.debug(f"收到一个无法匹配或已超时的 API 响应 (echo: {echo})")