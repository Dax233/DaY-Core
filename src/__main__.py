# src/__main__.py (最终修正版)
import asyncio
import signal

from .bot import Bot
from .logger import logger


async def main() -> None:
    """DaY-Core 的主异步入口.

    它负责启动机器人，并处理优雅的关闭流程。
    """
    # 初始化我们的机器人实例
    bot = Bot()

    # 创建一个关闭信号，这是一个 asyncio.Event 对象。
    # 我们的程序会一直等待，直到这个信号被设置。
    shutdown_signal = asyncio.Event()

    # 定义一个信号处理器，当收到 SIGINT (Ctrl+C) 或 SIGTERM 时，
    # 它会设置我们的关闭信号，从而让主程序知道是时候该退出了。
    def handle_signal(sig: signal.Signals) -> None:
        """处理操作系统信号的回调函数."""
        logger.info(f"收到关闭信号 {sig.name}，正在准备关闭...")
        shutdown_signal.set()

    # 获取当前的事件循环，并为关闭信号添加处理器。
    # 在 async 函数内部调用 get_running_loop 是绝对安全的。
    loop = asyncio.get_running_loop()
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal, sig)
    except NotImplementedError:
        # Windows 不完全支持 signal handler，但 Ctrl+C 依然能被 asyncio.run 捕获
        logger.warning("当前平台不支持 signal handler，将主要依赖 KeyboardInterrupt 进行关闭。")

    # 启动机器人核心服务 (这会启动 adapter 的后台任务)
    await bot.run()
    logger.info("核心服务已启动，DaY-Core 进入主循环，等待关闭信号...")

    try:
        # 主程序的核心就是等待这个关闭信号。
        # 只要这个信号不被 set()，程序就会永远在这里等待。
        await shutdown_signal.wait()
    finally:
        # 一旦等待结束（因为信号被设置了），我们就执行清理工作。
        logger.info("正在执行最后的清理工作...")
        await bot.stop()


# 程序的唯一入口
if __name__ == "__main__":
    try:
        # 使用 asyncio.run() 来启动我们的异步主函数。
        # 这是最推荐的方式，它会为我们处理好事件循环的一切。
        # 当 main() 函数返回或被中断时，asyncio.run() 会负责清理所有剩余任务。
        asyncio.run(main())
    except KeyboardInterrupt:
        # 在 Windows 或其他 asyncio.run 能直接捕获 KeyboardInterrupt 的情况下，
        # 我们会在这里看到一条消息，然后程序正常退出。
        logger.info("DaY-Core 已通过 KeyboardInterrupt 关闭。")

    logger.info("DaY-Core 已完全关闭。")
