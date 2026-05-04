# ScreenPlan — AI 智能学习规划助手

ScreenPlan 是一个全平台（macOS / Windows / Android）学习行为追踪与 AI 日程规划系统。通过追踪你在各设备上的应用使用行为，由后端 AI 自动分析并生成个性化学习计划。

## 架构

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ macOS Agent │  │Windows Agent│  │Android Agent│
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        │  HTTP :5051
                 ┌──────┴──────┐
                 │   后端 VPS    │
                 │ (Flask + AI) │
                 └─────────────┘
```

## 快速安装

### 方式一：下载预构建包（推荐）

| 平台 | 下载 | 说明 |
|---|---|---|
| 🖥 macOS | [ScreenPlan-v2.0.0-macos.zip](https://github.com/Sachika-GH/ScreenPlan/releases/latest/download/ScreenPlan-v2.0.0-macos.zip) | 解压后拖到 `/Applications`，双击启动 |
| 🪟 Windows | [ScreenPlan-v2.0.0-windows.zip](https://github.com/Sachika-GH/ScreenPlan/releases/latest/download/ScreenPlan-v2.0.0-windows.zip) | 解压后双击 `ScreenPlan.exe` |
| 📱 Android | [ScreenPlan-v2.0.0-android.apk](https://github.com/Sachika-GH/ScreenPlan/releases/latest/download/ScreenPlan-v2.0.0-android.apk) | 直接安装 APK |

### 方式二：从源码构建

参见下方各平台开发指南。

---

## 一、后端部署（Ubuntu VPS）

### 环境要求

- Ubuntu 20.04 / 22.04 / 24.04
- Python 3.10+
- 开放端口：**5051**（API）、**22**（SSH）

### 安装步骤

```bash
# 1. 将 backend/ 目录上传到 VPS
scp -r backend root@<你的VPS_IP>:/opt/screenplan-backend

# 2. SSH 到 VPS，运行安装脚本
ssh root@<你的VPS_IP>
bash /opt/screenplan-backend/deploy/ubuntu_install.sh
```

脚本会自动：安装 Python 依赖、创建 `screenplan` 用户、注册 systemd 服务并启动。

### 配置 JWT 密钥和 AI API Key

编辑 `/etc/systemd/system/screenplan.service`：

```bash
sudo nano /etc/systemd/system/screenplan.service
```

修改环境变量：

```
Environment="SCREENPLAN_JWT_SECRET=<随机64位hex>"
Environment="DEEPSEEK_API_KEY=<你的DeepSeek API Key>"
Environment="SCREENPLAN_LLM_API_BASE=https://api.deepseek.com/v1"
Environment="SCREENPLAN_LLM_MODEL=deepseek-chat"
```

应用更改：

```bash
sudo systemctl daemon-reload
sudo systemctl restart screenplan
```

### 验证部署

```bash
curl http://<你的VPS_IP>:5051/api/health
# → {"status":"ok","version":"0.1.0","uptime_seconds":120,"user_count":1}
```

### 防火墙

```bash
sudo ufw allow 5051/tcp
```

云服务商安全组/防火墙也需放行 5051 端口。

---

## 二、macOS 客户端

### 安装

1. 下载 [ScreenPlan-v2.0.0-macos.zip](https://github.com/Sachika-GH/ScreenPlan/releases/latest/download/ScreenPlan-v2.0.0-macos.zip)
2. 解压，将 `ScreenPlan.app` 拖入 `/Applications`
3. 双击启动

首次启动会弹出登录窗口。注册账号请访问 Web 面板（`http://<服务器IP>:5051`）。

### 功能

- **系统托盘图标**：菜单栏右侧，右键菜单操作
- **活动追踪**：每 3 分钟采样前台应用 + 浏览器标签 URL
- **AI 日程生成**：基于使用行为 + 日历事件生成每日学习计划
- **开机自启**：菜单中切换 "Auto-start"
- **离线容错**：网络中断时存储本地，恢复后自动上传

### 授权

系统偏好设置 → 隐私与安全性 → 辅助功能 → 添加 ScreenPlan

### 从源码运行

```bash
cd macos
pip3 install -r requirements.txt
python3 main.py tray
```

### 自行打包 .app

```bash
pip3 install py2app
cd macos
python3 setup.py py2app
# 产物在 dist/ScreenPlan.app
```

---

## 三、Windows 客户端

### 安装

1. 下载 [ScreenPlan-v2.0.0-windows.zip](https://github.com/Sachika-GH/ScreenPlan/releases/latest/download/ScreenPlan-v2.0.0-windows.zip)
2. 解压，双击 `ScreenPlan.exe`

首次启动弹出登录窗口（Web UI 同款配色）。注册账号请访问 Web 面板。

### 功能

- **系统托盘图标**：任务栏通知区，右键菜单操作
- **活动追踪**：每 3 分钟检测前台窗口进程
- **AI 日程生成**
- **开机自启**：菜单中切换，通过注册表实现
- **离线容错**

### 从源码运行

```bash
cd windows
pip install -r requirements.txt
python main.py tray
```

### 自行打包 .exe

```bash
pip install pyinstaller
cd windows
pyinstaller --onefile --windowed ^
  --add-data "config.json;." ^
  --hidden-import keyring.backends.Windows ^
  --hidden-import pystray._win32 ^
  --hidden-import win32gui ^
  --hidden-import win32process ^
  --hidden-import psutil ^
  --hidden-import network.auth_manager ^
  --hidden-import network.gateway ^
  --hidden-import network.sync_client ^
  --hidden-import network.autostart ^
  --hidden-import ui.tray_app ^
  --hidden-import ui.setup_window ^
  --name ScreenPlan ^
  main.py
```

CI 自动打包：[GitHub Actions](https://github.com/Sachika-GH/ScreenPlan/actions/workflows/build-windows.yml)

---

## 四、Android 客户端

### 安装

1. 下载 [ScreenPlan-v2.0.0-android.apk](https://github.com/Sachika-GH/ScreenPlan/releases/latest/download/ScreenPlan-v2.0.0-android.apk)
2. 开启「允许安装未知来源应用」
3. 安装后打开，登录或注册账号

### 必需权限

| 权限 | 设置路径 |
|---|---|
| 使用情况访问 | 设置 → 安全 → 使用情况访问权限 → ScreenPlan ✓ |
| 通知权限 | 首次启动自动弹窗请求（Android 13+） |
| 电池优化 | 设置 → 应用 → ScreenPlan → 电池 → 不限制 |

### 开机自启（防杀）

| 品牌 | 路径 |
|---|---|
| 小米/Redmi | 安全中心 → 应用管理 → 权限 → 自启动管理 → ScreenPlan ✓ |
| OPPO/一加 | 设置 → 应用 → 自启动 → ScreenPlan ✓ |
| vivo/iQOO | i管家 → 应用管理 → 权限管理 → 自启动 → ScreenPlan ✓ |
| 华为/荣耀 | 手机管家 → 应用启动管理 → ScreenPlan → 手动管理（全勾） |
| 三星/原生 | 设置 → 应用 → ScreenPlan → 电池 → 不限制 |

> 所有设备建议：最近任务中锁定 ScreenPlan，关闭电池优化。

### 自行编译

```bash
cd android
export ANDROID_HOME=~/Library/Android/sdk
export JAVA_HOME=/path/to/jdk17
./gradlew assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

---

## 五、Web 管理面板

后端自带 Web SPA，部署后直接访问：

```
http://<你的VPS_IP>:5051
```

功能：
- 📊 当日活动时间线（全设备聚合，swimlane 泳道图）
- 📈 学习 / 娱乐 / 其他分类统计
- 🤖 AI 每日学习计划（支持 Pomodoro）
- 👥 好友系统（共享使用数据和计划）
- 📱 设备管理（注册 / 编辑 / 删除）

---

## 六、配置说明

### 修改服务器地址

各端 `config.json` 中的 `server.url` 字段：

```json
{
  "server": {
    "url": "http://45.197.150.197:5051"
  }
}
```

优先级：`config.json` > `SCREENPLAN_SERVER_URL` 环境变量 > 局域网网关自动检测。

### 应用分类配置

`config.json` 中 `tracker.learning_apps` 和 `tracker.entertainment_apps` 列表控制应用分类。浏览器标签页中的娱乐域名由 `url_rules.entertainment_domains` 覆盖判定。

---

## 七、数据安全与重装

- **设备去重**：同一用户同平台只有一台设备记录。卸载重装后登录，自动复用原设备 ID，历史数据不会丢失。
- **离线队列**：网络中断时数据存入本地，恢复后自动批量上传。
- **JWT 认证**：30 天过期，密钥在服务端配置。

---

## 八、技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Flask + gunicorn + SQLite + PyJWT |
| AI | DeepSeek API（兼容 OpenAI 接口） |
| macOS | Python + rumps + pyobjc |
| Windows | Python + pystray + win32gui |
| Android | Kotlin + Jetpack Compose + Room + Hilt + WorkManager |
| Web | 原生 HTML/CSS/JS SPA |

---

## 九、常见问题

**Q: macOS 应用无法启动**  
A: 确认辅助功能权限已授予，并清理旧的 launchd plist（`~/Library/LaunchAgents/com.screenplan.*`）。

**Q: Android 通知栏不显示**  
A: Android 13+ 需授予通知权限。首次启动自动请求，或去设置 → 应用 → ScreenPlan → 通知 → 允许。

**Q: Android upload 不发送**  
A: 检查 Dashboard 上的 Device 状态是否为绿。若为红，重新走一遍登录+设备命名流程。

**Q: 重装后数据丢失**  
A: 不会。服务端按 `(user_id, platform)` 去重，同平台设备复用旧 ID，所有历史数据保留。

**Q: AI 计划生成失败**  
A: 确认 VPS 上已配置正确的 `DEEPSEEK_API_KEY`，且服务器可访问 DeepSeek API。

---

## License

MIT
