# src/plugin.py
import importlib
import pkgutil
from pathlib import Path
from typing import Set, TYPE_CHECKING

from .logger import logger

if TYPE_CHECKING:
    from .bot import Bot

class PluginManager:
    def __init__(self, bot: "Bot"):
        self.bot = bot
        # 使用集合来存储加载过的插件，防止重复加载
        self.loaded_plugins: Set[str] = set()

    def load_all_plugins(self):
        """加载所有插件目录下的插件。"""
        # 定义插件目录的路径
        human_plugin_dir = Path("plugins_human")
        ai_plugin_dir = Path("plugins_ai")

        logger.info("开始加载插件...")
        self._load_from_dir(human_plugin_dir)
        self._load_from_dir(ai_plugin_dir)
        logger.info(f"插件加载完毕，共加载了 {len(self.loaded_plugins)} 个插件。")

    def _load_from_dir(self, plugin_dir: Path):
        """从指定目录加载插件。"""
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