# plugins_human/file_plugin.py
from pathlib import Path

from src.adapters.base import Adapter
from src.api import API_FAILED
from src.bot import Bot  # 需要导入 Bot 来获取配置
from src.event import GroupMessageEvent
from src.logger import logger
from src.matcher import on_command
from src.message import Message


@on_command("/upload ").handle()
async def handle_upload_file(bot: Bot, adapter: Adapter, event: GroupMessageEvent) -> None:
    """处理文件上传命令.

    用法: /upload <文件名>
    文件名必须位于项目根目录下的、在 config.toml 中配置的 upload_dir 文件夹内.

    Args:
        bot (Bot): 机器人实例，用于获取配置.
        adapter (Adapter): 适配器实例，用于发送消息和上传文件.
        event (GroupMessageEvent): 群消息事件对象，包含触发此事件的用户信息和消息内容.
    """
    # 1. 解析文件名
    # 我们从 event.message 中提取纯文本，这样可以避免 @机器人 的情况污染命令
    command_text = event.message.get_plain_text()
    file_to_upload = command_text.replace("/upload", "").strip()

    if not file_to_upload:
        await adapter.send_message(
            event.group_id,
            "group",
            Message().text("请提供要上传的文件名哦！用法：/upload <文件名>"),
        )
        return

    # 2. 安全检查！
    # 从配置中获取允许的上传目录
    upload_dir_str = bot.config.upload_dir
    # 项目根目录
    project_root = Path(__file__).resolve().parent.parent
    # 构造安全的上传目录和目标文件路径
    safe_upload_path = (project_root / upload_dir_str).resolve()
    target_file_path = (safe_upload_path / file_to_upload).resolve()

    # 确保目标文件在我们允许的目录内，并且文件存在
    if not target_file_path.is_file() or safe_upload_path not in target_file_path.parents:
        logger.warning(
            f"文件上传被拒绝：'{target_file_path}' 不在允许的"
            f"目录 '{safe_upload_path}' 内或文件不存在。"
        )
        await adapter.send_message(
            event.group_id,
            "group",
            Message().text(f"找不到文件 '{file_to_upload}'，或者我没有权限访问它。"),
        )
        return

    # 3. 行使神权！
    logger.info(f"准备在群 {event.group_id} 中上传文件：{target_file_path}")
    result = await adapter.upload_group_file(
        group_id=event.group_id,
        file_path=str(target_file_path),
        file_name=file_to_upload,
    )

    # 4. 回报结果
    if result is not API_FAILED:
        await adapter.send_message(
            event.group_id, "group", Message().text(f"文件 '{file_to_upload}' 上传成功！")
        )
    else:
        await adapter.send_message(
            event.group_id,
            "group",
            Message().text("文件上传失败了... 可能是我没有权限或者文件太大了。T_T"),
        )
