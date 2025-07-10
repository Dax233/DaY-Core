# src/config.py
import datetime
import shutil
import sys
from pathlib import Path
from typing import Any

import tomlkit

# 我们需要从自己的 logger 导入
from .logger import logger

# --- 路径定义 ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_CONFIG_PATH = PROJECT_ROOT / "template" / "config_template.toml"
ACTUAL_CONFIG_PATH = PROJECT_ROOT / "config.toml"
BACKUP_DIR = PROJECT_ROOT / "config_backups"

BACKUP_DIR.mkdir(parents=True, exist_ok=True)


# --- 配置数据类 ---
class Config:
    """配置类，用于加载和存储应用程序的配置设置."""

    def __init__(self, data: dict[str, Any] | tomlkit.TOMLDocument) -> None:
        self.config_version: str = str(data.get("config_version", "0.0.0"))

        # Adapter Napcat Settings
        adapter_napcat_data = data.get("adapter", {}).get("napcat", {})
        self.adapter_host: str = str(adapter_napcat_data.get("host", "127.0.0.1"))
        self.adapter_port: int = int(adapter_napcat_data.get("port", 7094))

        # Core Settings
        core_data = data.get("core", {})
        self.debug: bool = bool(core_data.get("debug", True))
        self.log_level: str = str(core_data.get("log_level", "INFO")).upper()
        self.upload_dir: str = str(core_data.get("upload_dir", "uploads"))


_global_config: Config | None = None


def _merge_toml_data(
    new_data: tomlkit.TOMLDocument, old_data: tomlkit.TOMLDocument
) -> tomlkit.TOMLDocument:
    logger.info("正在尝试合并旧的配置值到新的配置模板...")
    for key in old_data:
        if key == "config_version":
            continue
        if key in new_data and isinstance(old_data[key], type(new_data[key])):
            if isinstance(new_data[key], tomlkit.items.Table):
                for sub_key in old_data[key]:
                    if sub_key in new_data[key] and isinstance(
                        old_data[key][sub_key], type(new_data[key][sub_key])
                    ):
                        new_data[key][sub_key] = old_data[key][sub_key]
            else:
                new_data[key] = old_data[key]
    return new_data


def _init_config() -> bool:
    if not TEMPLATE_CONFIG_PATH.exists():
        logger.critical(f"配置文件模板 {TEMPLATE_CONFIG_PATH} 未找到！程序无法继续。")
        sys.exit(1)

    template_doc = tomlkit.parse(TEMPLATE_CONFIG_PATH.read_text(encoding="utf-8"))
    expected_version = str(template_doc.get("config_version"))

    if not ACTUAL_CONFIG_PATH.exists():
        logger.warning(f"配置文件 {ACTUAL_CONFIG_PATH} 不存在，将从模板创建。")
        shutil.copy2(TEMPLATE_CONFIG_PATH, ACTUAL_CONFIG_PATH)
        logger.info(f"已创建新配置文件: {ACTUAL_CONFIG_PATH}，请根据需要修改后重新启动。")
        return True  # 需要退出

    actual_doc = tomlkit.parse(ACTUAL_CONFIG_PATH.read_text(encoding="utf-8"))
    actual_version = str(actual_doc.get("config_version"))

    if actual_version == expected_version:
        logger.info(f"配置文件版本 ({actual_version}) 无需更新。")
        return False  # 无需退出

    logger.warning(f"配置文件版本 ({actual_version}) 过旧，需要更新至 ({expected_version})。")
    backup_path = (
        BACKUP_DIR
        / f"config_v{actual_version}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.toml"
    )
    shutil.copy2(ACTUAL_CONFIG_PATH, backup_path)
    logger.info(f"旧配置文件已备份至: {backup_path}")

    updated_doc = _merge_toml_data(template_doc.copy(), actual_doc)
    ACTUAL_CONFIG_PATH.write_text(tomlkit.dumps(updated_doc), encoding="utf-8")
    logger.info("配置文件已更新。请检查新配置项，然后重新启动。")
    return True  # 需要退出


def get_config() -> Config:
    """获取全局配置实例."""
    global _global_config
    if _global_config:
        return _global_config

    if _init_config():
        sys.exit(0)

    try:
        config_dict = tomlkit.parse(ACTUAL_CONFIG_PATH.read_text(encoding="utf-8"))
        _global_config = Config(config_dict)
        logger.info(f"配置已从 {ACTUAL_CONFIG_PATH} 加载。")
        return _global_config
    except Exception as e:
        logger.critical(f"加载配置文件失败: {e}", exc_info=True)
        sys.exit(1)
