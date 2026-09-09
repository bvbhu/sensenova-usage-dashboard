#!/bin/bash
# ============================================================
# macOS 一键打包脚本 —— 把程序打成独立 .app（免装 Python 即可双击运行）
# ⚠️ 必须在 macOS 上运行（PyInstaller 无法在 Windows/Linux 上交叉编译 Mac 包）
#
# 前置要求（只需首次）：
#   1. 安装「framework 版」Python（系统自带的 /usr/bin/python3 不行！）
#       推荐： brew install python        （Homebrew 版就是 framework 构建）
#       或去 https://python.org 下载安装包
#   2. 本脚本会自动 pip 安装依赖（含 pyobjc，pywebview 在 Mac 的 Cocoa 后端依赖它）
#
# 用法：
#   chmod +x build_mac.sh
#   ./build_mac.sh
#
# 产物： dist/SenseNova用量查询.app   ← 这就是可分发应用
#        双击即可运行；可拖进「应用程序」文件夹长期使用
#        首次运行自动在可执行文件旁边（或 ~/Library/Application Support 下）生成
#        accounts.json，在窗口内填写用户名 + 密码即可
# ============================================================

set -e
cd "$(dirname "$0")"

# 图标必须存在（生成脚本 make_icon_mac.py 已移除，请直接用仓库里的 app.icns）
if [ ! -f "app.icns" ]; then
  echo "------------------------------------------------------------"
  echo "⚠️  未找到 app.icns，且图标生成脚本已移除！"
  echo "请先把 app.icns 放到本目录再打包。"
  echo "------------------------------------------------------------"
  exit 1
fi

PYTHON=$(command -v python3 || command -v python)
echo "使用 Python: $PYTHON"

# 检测是否为 framework 构建（pywebview 在 macOS 上必须有 framework Python，否则运行时崩溃）
if ! "$PYTHON" -c "import sys; p=sys.executable; assert ('framework' in p) or ('Python.framework' in p) or ('Cellar' in p) or ('opt/homebrew' in p), 'not framework'" 2>/dev/null; then
  echo "------------------------------------------------------------"
  echo "⚠️  当前 python3 不是 framework 构建，pywebview 无法运行！"
  echo "请改用 Homebrew 安装的 python3："
  echo "    brew install python"
  echo "    # 安装后重新打开终端，确认 which python3 指向 /opt/homebrew 或 /usr/local"
  echo "------------------------------------------------------------"
  exit 1
fi

echo "安装/更新依赖..."
"$PYTHON" -m pip install --quiet --upgrade \
  requests PyJWT tabulate pywebview pyinstaller \
  pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-WebKit

APP="SenseNova用量查询"
APP_BUNDLE="dist/$APP.app"
MACOS_DIR="$APP_BUNDLE/Contents/MacOS"

echo "开始打包（onedir + windowed → 生成 .app，图标 app.icns）..."

"$PYTHON" -m PyInstaller --noconfirm --onedir --windowed \
  --name "$APP" \
  --icon "app.icns" \
  --osx-bundle-identifier "com.sensenova.usage" \
  --collect-all webview \
  --hidden-import webview.platforms.cocoa \
  --hidden-import pyobjc \
  --hidden-import requests \
  --hidden-import jwt \
  dashboard.py

echo "写入空白账号模板到 .app（不含任何真实 Token，首次运行也可在窗口内填写）..."
mkdir -p "$MACOS_DIR"
cat > "$MACOS_DIR/accounts.json" <<'EOF'
{
  "accounts": [
    {"username": "", "password": "", "jwt_token": ""}
  ]
}
EOF

echo "写入版本信息到 Info.plist..."
PLIST="$APP_BUNDLE/Contents/Info.plist"
if [ -f "$PLIST" ]; then
  /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString 1.0.0" "$PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string 1.0.0" "$PLIST"
  /usr/libexec/PlistBuddy -c "Set :CFBundleVersion 1.0.0" "$PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string 1.0.0" "$PLIST"
  /usr/libexec/PlistBuddy -c "Set :CFBundleIconFile app" "$PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string app" "$PLIST"
  echo "  版本号已设为 1.0.0"
fi

echo "尝试 ad-hoc 签名（绕过 Gatekeeper 拦截，失败不影响使用）..."
codesign --force --deep --sign - "$APP_BUNDLE" 2>/dev/null \
  && echo "  已签名" \
  || echo "  （可选）codesign 不可用，跳过；首次打开请右键 → 打开"

echo ""
echo "✅ 打包完成！"
echo "   应用： $(pwd)/$APP_BUNDLE"
echo "   使用：双击 .app 即可；或拖入「应用程序」文件夹长期使用"
echo "   若提示「无法验证开发者」：右键 .app → 打开，即可永久放行"
echo "   配置：窗口内展开「账号配置」→ 填用户名 + 密码 → 点登录"
