# src/plugin.py
import importlib
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

from .logger import logger

if TYPE_CHECKING:
    from .bot import Bot

# 定义一个清晰的项目根目录常量，供所有插件使用
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class PluginManager:
    """插件管理器.

    负责发现、加载和管理所有插件。
    它会在指定的插件目录 (`plugins_human`, `plugins_ai`) 中搜索合法的 Python 模块，
    并将其作为插件进行加载。

    Attributes:
        bot (Bot): Bot 实例的引用。
        loaded_plugins (Set[str]): 一个集合，用于存放所有已成功加载的插件的名称，以防止重复加载。
    """

    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        # 使用集合来存储加载过的插件，防止重复加载
        self.loaded_plugins: set[str] = set()

    def load_all_plugins(self) -> None:
        """加载所有插件目录下的插件."""
        # 使用 PROJECT_ROOT 来构造绝对路径
        human_plugin_dir = PROJECT_ROOT / "plugins_human"
        ai_plugin_dir = PROJECT_ROOT / "plugins_ai"

        logger.info("开始加载插件...")
        self._load_from_dir(human_plugin_dir)
        self._load_from_dir(ai_plugin_dir)
        logger.info(f"插件加载完毕，共加载了 {len(self.loaded_plugins)} 个插件。")

    def _load_from_dir(self, plugin_dir: Path) -> None:
        """从指定目录加载插件."""
        if not plugin_dir.is_dir():
            logger.warning(f"插件目录 {plugin_dir} 不存在，已跳过。")
            return

        # 遍历目录下的所有模块
        for module_info in pkgutil.iter_modules([str(plugin_dir)]):
            module_name = f"{plugin_dir.name}.{module_info.name}"
            if module_name in self.loaded_plugins:
                continue

            try:
                # 动态导入模块
                importlib.import_module(module_name)
                self.loaded_plugins.add(module_name)
                logger.info(f"  - 成功加载插件: {module_name}")
            except Exception as e:
                logger.error(f"  - 加载插件 {module_name} 失败: {e}", exc_info=True)
