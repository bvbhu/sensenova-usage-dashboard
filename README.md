# SenseNova 用量查询工具

商汤日日新（SenseNova，platform.sensenova.cn）多账号 Token Plan 资源包用量查询工具。  
解决「不想每天登录平台查看各账号剩余额度」的痛点：桌面原生窗口实时查看，每 5 分钟自动刷新。

---

## 功能特性

- **桌面应用**（`dashboard.py`）：双击即弹出原生窗口，内嵌网页 UI，展示各账号积分池用量（5 小时 / 7 天窗口），**每 5 分钟自动刷新**，窗口内可直接配置账号。
- **账号密码自动登录**：在「账号配置」面板填入**账号（用户名/邮箱）+ 密码**，工具自动完成 OAuth2 授权码 + PKCE 登录流程、抓取并存储 JWT（密码以 RSA-OAEP + A256GCM 加密传输，与网页端一致），**JWT 过期后自动用账号密码重登**，无需再手动从浏览器 F12 复制。
- **兼容手动粘贴 JWT**：仍可像以前一样直接粘贴从浏览器复制的 JWT。
- **多账号支持**：账号、密码、JWT 统一维护在 `accounts.json`。
- **跨平台打包**：Windows 已打包为单文件 exe；macOS 可通过 `build_mac.sh` 一键打成 `.app`。

---

## 目录结构

```
用量查询/
├── dashboard.py              # 桌面应用主程序（pywebview 原生窗口 + 内置 HTTP 服务）
├── auth_login.py             # 账号密码自动登录模块（OAuth2 授权码 + PKCE + 密码 JWE 加密）
├── 启动.bat                  # Windows 双击启动（无控制台窗口）
├── 启动.sh                  # macOS / Linux 启动脚本（优先运行已打包二进制，否则源码模式）
├── build_mac.sh             # macOS 一键打包为 .app
├── app.ico                  # Windows 应用图标
├── app.icns                 # macOS 应用图标
├── version_info.txt          # Windows exe 版本信息资源
├── SenseNova用量查询.spec    # PyInstaller 打包配置（Windows）
├── accounts.json            # 账号 / 密码 / JWT 配置（含明文凭据，勿提交到公开仓库）
├── dist/                    # 已打包成品（首次运行自动生成 accounts.json）
│   └── SenseNova用量查询.exe
└── .workbuddy/              # 项目记忆（非代码，勿删）
```

> 构建过程中产生的 `__pycache__/`、`build/` 为可重新生成的中间/缓存目录，已清理。  
> 重新打包时会自动生成，无需纳入版本管理。

---

## 快速开始

### 桌面应用（推荐日常使用）

**Windows**：双击 `启动.bat`，或运行已打包的 `dist/SenseNova用量查询.exe`（纯 exe 即可独立运行，首次启动自动生成 `accounts.json`）。

**macOS / Linux**：

```bash
chmod +x 启动.sh
./启动.sh
```

---

## 配置账号

工具支持两种认证方式，任选其一（也可以混用，每个账号各选一种）。

### 方式一：账号密码自动登录（推荐）

在「账号配置」面板：

1. 填 **用户名**（平台登录用户名 / 邮箱，如 `shaobingtongzhi`）
2. 填 **密码**
3. 点 **登录** → 工具自动完成登录、抓取 JWT 并存储

JWT 约 3 小时过期，过期后工具会用保存的账号密码**自动重新登录**，你无需任何操作。窗口内只显示用户名，JWT 内容不再展示。

> 密码安全性：传输时按网页端同样的方式加密——用平台 JWKS 公钥做 `RSA-OAEP` + `A256GCM` 的 JWE 加密，明文密码不会直接出现在请求中。但 `accounts.json` 里仍以**明文**保存用户名密码（为支持自动重登），请勿提交到公开仓库或他人可读取的位置。

获取步骤：

1. 浏览器登录 <https://platform.sensenova.cn>
2. 按 `F12` → **Network** 标签 → 刷新页面  
   `accounts.json` 格式：

```json
{
  "accounts": [
    { "username": "shaobingtongzhi", "password": "明文密码", "jwt_token": "登录后自动写入" }
  ]
}
```



> 说明：大队长明确表示没有大装置 AK/SK，工具仅使用 JWT 认证，无需配置 AK/SK。

---

## 构建 / 打包

### 环境要求（Requirements）

**操作系统**
- Windows 10 / 11（桌面应用主目标）
- macOS 11+（如需打包 `.app`）
- 任意 Linux（仅支持源码运行，不提供官方打包）

**Python 解释器**
- 版本：3.8 – 3.13 任意版本均可（已验证 3.9 / 3.13）
- 环境：conda 环境、venv、或系统 Python 皆可，只要能 `pip install` 下列依赖
- 一台可联网第一次拉取依赖的机器

**Windows 必需系统组件**
- **Microsoft Edge WebView2 Runtime**：`pywebview` 在 Windows 默认使用 Edge 内核。绝大多数 Win10/11 已自带；若运行 exe 报「WebView2 未安装」，去微软官网下载 Evergreen Bootstrapper 安装即可。

**Python 依赖**

| 包 | 用途 | 何时需要 |
|---|---|---|
| `pywebview` | 原生窗口 GUI（内嵌网页 UI） | 运行 + 打包 |
| `jwcrypto` | 密码 JWE 加密（RSA-OAEP + A256GCM）、JWT 解析 | 运行 + 打包 |
| `requests` | HTTP 请求 | 运行 + 打包 |
| `pyinstaller` | 打包成单文件 exe / .app | 仅打包 |

> 源码**未使用** PyJWT，打包时无需安装；`.spec` 也只 `hiddenimport` 了 `requests` / `jwcrypto` / `auth_login`。

### 打包步骤（Windows，通用）

任意装有上述依赖的 Python 解释器即可，命令与具体路径无关：

```bat
:: 1) 进入项目根目录（即本 README 所在目录）
cd /d <项目根目录>

:: 2) 内存紧张时设置，避免 OpenBLAS 线程分配导致子进程崩溃
set OPENBLAS_NUM_THREADS=1
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1

:: 3) 用你的 Python 跑 PyInstaller；.spec 已内含 all 配置，无需在命令行重复指定
<PYTHON> -m PyInstaller "SenseNova用量查询.spec" --noconfirm
```

把 `<PYTHON>` 替换成你实际用的解释器绝对路径，例如：
- conda 环境：`D:\ProgramData\miniconda3\envs\pv_forecast\python.exe`
- venv：`C:\...\envs\default\Scripts\python.exe`
- 系统 Python：直接写 `python`（需已 `pip install` 上述依赖）

产物为 `dist/SenseNova用量查询.exe`（约 19MB，含 Python + 依赖 + 图标 + 版本信息），可独立分发。

### 关键注意事项

1. **打包前先移开旧 exe（重要）**  
   某些环境下「删除旧 exe」会被安全软件 / 沙箱钩子拦截，导致 PyInstaller 在写入新文件前中止、旧 exe 时间戳不变。用 rename 挪开即可避免：
   ```bat
   move "dist\SenseNova用量查询.exe" "_old.exe"
   ```
   再执行上面的打包命令。

2. **`.spec` 已包含全部打包配置**，无需在命令行重复指定：  
   `--onefile --windowed --icon=app.ico --version-file=version_info.txt --collect-all webview`，以及 `hiddenimports=['requests','jwcrypto','auth_login']`。直接 `pyinstaller <spec>` 即可。

3. **macOS 打包必须在本机**（PyInstaller 不支持交叉编译），用 `build_mac.sh`。需 **framework 版 Python**（如 Homebrew 的 `python3`）；系统自带 `python3` 不行（pywebview 的 Cocoa 后端依赖 framework 版）。脚本会自动写入空白配置模板并做 ad-hoc 签名。

### 一键安装依赖（参考）

```bat
<PYTHON> -m pip install pywebview jwcrypto requests pyinstaller
```

---

## 依赖

- **运行 / 打包均需**：`requests`、`pywebview`、`jwcrypto`（密码 JWE 加密 + JWT 解析）
- **仅打包需要**：`pyinstaller`（Windows）；`pyinstaller` + `pyobjc-core` / `pyobjc-framework-Cocoa` / `pyobjc-framework-WebKit`（macOS）
- 源码未使用 PyJWT，无需安装；`.spec` 仅 `hiddenimport` 了 `requests` / `jwcrypto` / `auth_login`

---

## API

- 接口：`GET https://platform.sensenova.cn/lite/console/v1/tokenplan/pool-usage`
- 认证：请求头 `Authorization: Bearer <JWT>`
- 返回：各积分池的 `name`、`model_ids`、`window_5h` / `window_7d`（含 `limit` / `used` / `remaining` / `reset_at`）、`grant_balance`、`nearest_grant_expiry`、`pool_type`（default / dedicated）
