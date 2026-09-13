#!/bin/bash
# SenseNova 用量查询 - macOS / Linux 启动脚本
# 用法：
#   1. 赋可执行权限： chmod +x 启动.sh
#   2. 双击本文件（或在终端执行 ./启动.sh）即可打开原生窗口
#
# 说明：
#   - 若当前目录已存在打包好的二进制『SenseNova用量查询』，则直接运行它
#   - 否则退回到源码模式：自动装依赖并运行 python3 dashboard.py
#   - macOS 需要 framework 版 Python（pywebview 的 Cocoa 后端依赖）：
#       ✅ Homebrew python3: brew install python
#       ✅ python.org 安装包: https://www.python.org/downloads/
#       ❌ 系统自带 /usr/bin/python3（非 framework）
#       ❌ conda/miniconda 环境（非 framework 构建）

cd "$(dirname "$0")"

# 优先运行已打包的二进制
APP_BIN="$(dirname "$0")/SenseNova用量查询"
if [ -x "$APP_BIN" ]; then
  exec "$APP_BIN"
fi

# ============================================================
# 选择 Python 解释器
# macOS: pywebview 需要 framework 构建的 Python，否则启动即崩溃。
#   conda/miniforge 环境的 PYTHONFRAMEWORK 为空，不能直接用。
#   策略：当前 Python 是 framework → 直接用；否则去找 Homebrew python3。
# ============================================================
_find_python() {
  local best=""
  for cmd in python3 python /usr/local/bin/python3 /opt/homebrew/bin/python3 \
             /Library/Frameworks/Python.framework/Versions/3.*/bin/python3; do
    local p
    p=$(command -v "$cmd" 2>/dev/null) || p="$cmd"
    [ -x "$p" ] || continue
    local fw
    fw=$("$p" -c "import sysconfig; print(sysconfig.get_config_var('PYTHONFRAMEWORK') or '')" 2>/dev/null)
    if [ "$fw" != "" ]; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
  if [ "$(uname)" = "Darwin" ]; then
    echo "未找到 python3，请先安装 framework 版 Python："
    echo "  brew install python"
    echo "  或从 https://www.python.org/downloads/ 下载"
  fi
  exit 1
fi

# macOS: 检查当前 Python 是否为 framework 构建
if [ "$(uname)" = "Darwin" ]; then
  FW=$( "$PYTHON" -c "import sysconfig; print(sysconfig.get_config_var('PYTHONFRAMEWORK') or '')" 2>/dev/null )
  if [ "$FW" = "" ]; then
    echo "------------------------------------------------------------"
    echo "当前 Python 不是 framework 构建，pywebview 无法运行！"
    echo "  当前 Python: $PYTHON"
    echo "  （conda / miniforge 环境均非 framework 构建，不适用）"
    echo "正在寻找系统上的 framework 版 Python ..."
    FW_PYTHON=$( _find_python )
    if [ -n "$FW_PYTHON" ]; then
      echo "找到 framework 版 Python: $FW_PYTHON"
      PYTHON="$FW_PYTHON"
    else
      echo "未找到 framework 版 Python。请任选其一安装后重试："
      echo "  1) Homebrew（推荐）: brew install python"
      echo "  2) python.org 安装包: https://www.python.org/downloads/"
      echo "------------------------------------------------------------"
      exit 1
    fi
    echo "------------------------------------------------------------"
  fi
fi

# 依赖自检，缺失则自动安装（首次运行会联网安装）
# 实际依赖：requests, pywebview, jwcrypto（jwcrypto 又依赖 cryptography）
$PYTHON -c "import requests, webview, jwcrypto; from cryptography import x509" 2>/dev/null || {
  echo "首次运行，正在安装依赖（requests / cryptography / jwcrypto / pywebview）..."
  $PYTHON -m pip install --default-timeout=120 --only-binary=cryptography requests cryptography jwcrypto pywebview
  if [ $? -ne 0 ]; then
    echo "依赖安装失败，请手动执行："
    echo "  $PYTHON -m pip install requests cryptography jwcrypto pywebview"
    exit 1
  fi
}

echo "正在启动 SenseNova 用量查询窗口..."
echo "  Python: $PYTHON"
exec "$PYTHON" dashboard.py
