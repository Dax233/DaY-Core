# src/logger.py
from loguru import logger

# 这里可以先用最简单的配置，之后再把它变得像AIcarus里那么华丽
logger.add(
    "logs/day-core_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    level="DEBUG",
)

# 导出 logger 实例
__all__ = ["logger"]
