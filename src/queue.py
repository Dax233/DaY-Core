# src/queue.py
import asyncio

# 这个队列就是我们的“中转站”，所有来自 Napcat 的原始数据都先到这里排队
raw_event_queue = asyncio.Queue()
