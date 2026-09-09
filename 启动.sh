#!/bin/bash
# SenseNova 用量查询 - macOS / Linux 启动脚本
# 用法：
#   1. 赋可执行权限： chmod +x 启动.sh
#   2. 双击本文件（或在终端执行 ./启动.sh）即可打开原生窗口
#
# 说明：
#   - 若当前目录已存在打包好的二进制『SenseNova用量查询』，则直接运行它
#   - 否则退回到源码模式：自动装依赖并运行 python3 dashboard.py
#   - macOS 请用 framework 版 Python（Homebrew 或 python.org），系统自带 python3 不行

cd "$(dirname "$0")"

# 优先运行已打包的二进制
APP_BIN="$(dirname "$0")/SenseNova用量查询"
if [ -x "$APP_BIN" ]; then
  exec "$APP_BIN"
fi

PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
  echo "未找到 python3，请先安装：brew install python 或从 https://python.org 下载"
  exit 1
fi

# 依赖自检，缺失则自动安装（首次运行会联网安装）
$PYTHON -c "import requests, webview, jwt" 2>/dev/null || {
  echo "首次运行，正在安装依赖（requests / PyJWT / tabulate / pywebview）..."
  $PYTHON -m pip install --quiet --upgrade requests PyJWT tabulate pywebview
  if [ $? -ne 0 ]; then
    echo "依赖安装失败，请手动执行："
    echo "  $PYTHON -m pip install requests PyJWT tabulate pywebview"
    exit 1
  fi
}

echo "正在启动 SenseNova 用量查询窗口..."
exec "$PYTHON" dashboard.py
