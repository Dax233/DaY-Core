# src/plugin.py
import importlib
from pathlib import Path
from typing import TYPE_CHECKING

import tomlkit

from .logger import logger

if TYPE_CHECKING:
    from pydantic import BaseModel

    from .bot import Bot

# --- 统一的插件配置目录 ---
# 所有插件的配置文件都会被自动创建在这里
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_CONFIGS_DIR = PROJECT_ROOT / "configs" / "plugins"
PLUGIN_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)


class PluginManager:
    """插件管理器.

    负责发现、加载和管理所有插件。
    它会在指定的插件目录中搜索合法的 Python 模块，并将其作为插件进行加载.
    更重要的是，它会为每个包含 config.py 的插件，自动处理其配置文件的生成与加载.

    Attributes:
        bot (Bot): 关联的 Bot 实例，用于访问核心功能和配置.
        loaded_plugins (set[str]): 已加载的插件名称集合，避免重复加载.
    """

    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.loaded_plugins: set[str] = set()

    def load_all_plugins(self) -> None:
        """加载所有插件目录下的插件."""
        human_plugin_dir = PROJECT_ROOT / "plugins_human"
        ai_plugin_dir = PROJECT_ROOT / "plugins_ai"

        logger.info("开始加载插件...")
        self._load_from_dir(human_plugin_dir)
        self._load_from_dir(ai_plugin_dir)
        logger.info(f"插件加载完毕，共加载了 {len(self.loaded_plugins)} 个插件。")

    def _load_from_dir(self, plugin_dir: Path) -> None:
        """从指定目录加载插件，并自动处理其配置."""
        if not plugin_dir.is_dir():
            logger.warning(f"插件目录 {plugin_dir} 不存在，已跳过。")
            return

        for item in plugin_dir.iterdir():
            if not item.is_dir() or item.name.startswith(("_", ".")):
                continue

            if not (item / "__init__.py").exists():
                continue

            module_name = f"{plugin_dir.name}.{item.name}"
            if module_name in self.loaded_plugins:
                continue

            try:
                # --- 这是由框架承担的、优雅的配置处理流程 ---
                # 1. 尝试导入插件的 config 子模块，而不立即导入主模块
                config_model = None
                try:
                    config_module_name = f"{module_name}.config"
                    config_module = importlib.import_module(config_module_name)

                    # 约定插件的配置模型类名为 'Config'
                    if hasattr(config_module, "Config"):
                        config_model = config_module.Config
                        logger.debug(f"插件 {module_name} 发现了 Config 模型。")

                except ImportError:
                    logger.debug(
                        f"插件 {module_name} 没有 config.py 文件或Config类，跳过配置加载。"
                    )
                except Exception as e:
                    logger.opt(exception=e).error(f"导入插件 {module_name} 的配置模块时出错。")

                # 2. 如果找到了 Config 模型，就由框架来处理它的配置文件
                if config_model:
                    self._handle_plugin_config(module_name, config_model)

                # 3. 最后再安全地导入插件的主模块 (__init__.py)
                importlib.import_module(module_name)
                self.loaded_plugins.add(module_name)
                logger.info(f"  - 成功加载插件: {module_name}")

            except Exception as e:
                logger.error(f"  - 加载插件 {module_name} 失败: {e}", exc_info=True)

    def _handle_plugin_config(self, module_name: str, config_model: type["BaseModel"]) -> None:
        """由框架统一处理插件的配置文件生成与加载."""
        config_filename = f"{module_name}.toml"
        config_path = PLUGIN_CONFIGS_DIR / config_filename

        try:
            if not config_path.exists():
                logger.warning(f"插件 {module_name} 的配置文件不存在，将自动生成...")

                doc = tomlkit.document()
                # --- 核心修正点在这里！ ---
                # 正确的方式：使用 tomlkit 提供的工厂函数！
                # tomlkit.comment() 会创建一个 doc.add() 能正确理解的、可以独立成行的注释对象
                doc.add(tomlkit.comment("由 DaY-Core 自动生成的插件配置文件"))
                doc.add(tomlkit.comment(f"插件: {module_name}"))
                doc.add(tomlkit.nl())  # tomlkit.nl() 用于创建一个换行

                schema = config_model.model_json_schema()

                for prop_name, prop_details in schema.get("properties", {}).items():
                    comment_str = prop_details.get("description", "无描述")
                    default_value = prop_details.get("default", None)

                    # --- 核心修复点：使用更结构化的方式构建 Item ---
                    # 1. 根据默认值的类型，创建对应的 tomlkit Item
                    #    这是一个简化的类型映射，可以根据需要扩展
                    if isinstance(default_value, str):
                        item = tomlkit.string(default_value)
                    elif isinstance(default_value, bool):
                        item = tomlkit.boolean(default_value)
                    elif isinstance(default_value, int):
                        item = tomlkit.integer(default_value)
                    elif isinstance(default_value, float):
                        item = tomlkit.float_(default_value)
                    elif isinstance(default_value, list):
                        item = tomlkit.array()
                        for i in default_value:
                            item.append(i)
                    elif isinstance(default_value, dict):
                        item = tomlkit.inline_table()
                        item.update(default_value)
                    elif default_value is None:
                        # 对于 None，我们特殊处理，因为 TOML 没有标准的 null
                        # 通常表示为键不存在或留空。这里我们直接添加一个空字符串
                        item = tomlkit.string("")
                    else:
                        # 对于未知类型，转为字符串
                        item = tomlkit.string(str(default_value))

                    # 2. 将注释附加到这个 Item 上
                    item.comment(comment_str)

                    # 3. 将键和这个构造好的 Item 添加到文档中
                    doc.add(prop_name, item)
                    # 在每个配置项后面也加个换行，让格式更好看
                    doc.add(tomlkit.nl())

                with config_path.open("w", encoding="utf-8") as f:
                    f.write(tomlkit.dumps(doc))
                logger.success(f"已为插件 {module_name} 创建默认配置文件: {config_path}")

            with config_path.open("r", encoding="utf-8") as f:
                loaded_data = tomlkit.load(f)

            # 过滤掉非键值对的项，比如注释和换行
            config_data = {
                k: v
                for k, v in loaded_data.items()
                if isinstance(
                    v, str | int | float | bool | list | dict | tomlkit.items.Table
                )  # 修正: tomlkit的table也算
            }

            # 兼容 pydantic v2 的加载方式
            if hasattr(config_model, "model_validate"):
                validated_config = config_model.model_validate(config_data)
            else:  # 兼容 pydantic v1
                validated_config = config_model(**config_data)

            self.bot.plugin_configs[module_name] = validated_config

        except Exception as e:
            # Pydantic 校验失败时，validated_config 不会被赋值，所以 get_plugin_config 会返回 None
            logger.opt(exception=e).error(f"处理插件 {module_name} 的配置时出错！")
