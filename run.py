# run.py
import sys
import os
import runpy

# 把项目根目录加到 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 直接用 runpy 模块来运行 src 包，这才是最 Pythonic 的方式！
# 它会自动执行 src/__main__.py
if __name__ == "__main__":
    runpy.run_module("src", run_name="__main__")