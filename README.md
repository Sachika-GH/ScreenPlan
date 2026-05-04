# ScreenPlan — AI 智能学习规划助手

ScreenPlan 是一个全平台（macOS / Windows / Android）学习行为追踪与 AI 日程规划系统。通过追踪你在各设备上的应用使用行为，由后端 AI（DeepSeek）自动分析并生成个性化学习计划。

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ macOS Agent │  │Windows Agent│  │Android Agent│
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        │  HTTP :5051
                 ┌──────┴──────┐
                 │ Ubuntu VPS  │
                 │  (Backend)  │
                 └─────────────┘
```

---

## 项目结构

```
ScreenPlan/
├── backend/          # Flask 后端（部署在 Ubuntu VPS）
│   ├── api/          #   REST 路由 (auth/device/usage/schedule/friend)
│   ├── deploy/       #   systemd + nginx 部署文件
│   ├── static/       #   Web SPA 前端
│   ├── app.py        #   Flask 入口
│   └── requirements.txt
├── macos/            # macOS 状态栏应用 + 后台服务
│   ├── deploy/       #   launchd plist 文件
│   ├── network/      #   网络同步、认证、网关检测
│   ├── ui/           #   托盘 UI (rumps)
│   └── main.py       #   入口 (setup/tray/daemon)
├── windows/          # Windows 系统托盘应用
│   ├── deploy/       #   Windows 服务/启动脚本
│   ├── network/      #   网络同步
│   └── main.py       #   入口
└── android/          # Android 追踪应用 (Kotlin + Jetpack Compose)
    ├── app/          #   应用代码
    └── build.gradle.kts
```

---

## 一、后端部署（Ubuntu VPS）

后端负责接收所有客户端上传的活动数据，提供 AI 日程生成和 Web 管理面板。

### 环境要求

- Ubuntu 20.04 / 22.04 / 24.04
- Python 3.10+
- 开放的端口：**5051** (API), **22** (SSH), ~~6374~~ (SSH 如更换)

### 安装步骤

```bash
# 1. 将后端代码上传到 VPS
scp -r backend root@<你的VPS_IP>:/opt/

# 2. SSH 到 VPS，运行一键安装脚本
ssh root@<你的VPS_IP>
bash /opt/backend/deploy/ubuntu_install.sh
```

脚本会自动完成：
- 安装 Python 依赖（Flask + gunicorn）
- 创建 `screenplan` 系统用户
- 注册 systemd 服务并启动

### 部署后检查

```bash
# 查看服务状态
systemctl status screenplan

# 查看日志
journalctl -u screenplan -f

# 本地测试
curl http://localhost:5051/api/health

# 公网测试
curl http://<你的VPS_IP>:5051/api/health
```

### 修改 JWT 密钥

编辑 `/etc/systemd/system/screenplan.service`，修改 `SCREENPLAN_JWT_SECRET`：

```bash
sudo nano /etc/systemd/system/screenplan.service
# 找到 SCREENPLAN_JWT_SECRET，改为随机 64 位 hex
sudo systemctl daemon-reload
sudo systemctl restart screenplan
```

### 防火墙开放端口

```bash
# 如果使用了云服务商的安全组/防火墙，也需要在控制台放行 5051
sudo ufw allow 5051/tcp
```

---

## 二、macOS 客户端部署

macOS 客户端包含两部分：
- **daemon**：后台活动追踪（每 3 分钟采样应用窗口）
- **tray**：状态栏图标 + 右键菜单（查看 Dashboard / 计划 / 启停追踪）

### 环境要求

- macOS 10.15+ (Python 3.9+)
- 辅助功能权限（系统偏好设置 → 隐私与安全性 → 辅助功能 → 添加 Terminal/Python）

### 安装步骤

```bash
# 1. 进入 macOS 项目目录
cd macos

# 2. 安装 Python 依赖
pip3 install -r requirements.txt

# 3. 修改后端地址
# 编辑 config.json，将 url 改为你的 VPS 地址
# "url": "http://<你的VPS_IP>:5051"

# 4. 首次设置（注册/登录账号 + 注册设备）
python3 main.py setup

# 5. 安装 launchd 服务（开机自启）
cd deploy
bash install_launchd.sh
```

### 手动启动/停止

```bash
# 启动后台追踪
python3 main.py daemon

# 启动状态栏（会自动启动 daemon）
python3 main.py tray

# 停止所有服务
launchctl unload ~/Library/LaunchAgents/com.screenplan.agent.plist
launchctl unload ~/Library/LaunchAgents/com.screenplan.tray.plist
```

### 查看运行日志

```bash
tail -f data/launchd.log    # daemon 日志
tail -f data/tray.log       # tray 日志
```

---

## 三、Windows 客户端部署

### 环境要求

- Windows 10 / 11
- Python 3.9+
- 需安装 Python 后添加到 PATH

### 安装步骤

```bash
# 1. 进入 Windows 项目目录
cd windows

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 修改后端地址
# 编辑 config.json，将 url 改为你的 VPS 地址
# "url": "http://<你的VPS_IP>:5051"

# 4. 首次设置（注册/登录账号 + 注册设备）
python main.py setup

# 5. 启动（按需）
python main.py tray    # 带系统托盘的完整模式
python main.py daemon  # 仅后台追踪

# 6. 配置开机自启
# 将 deploy/install_windows.bat 快捷方式放入启动文件夹：
# Win+R → shell:startup → 粘贴快捷方式
```

### 管理服务

系统托盘右键菜单提供：
- **Open Dashboard** — 打开 Web 管理面板
- **Start / Stop Tracking** — 启停追踪
- **View Schedule** — 查看 AI 计划
- **Quit** — 退出

---

## 四、Android 客户端部署

### 安装方式一：下载 APK 直接安装

1. 下载 [ScreenPlanAgent-v1.0.0.apk](https://github.com/<你的用户名>/ScreenPlan/releases) 到手机
2. 安装前开启「允许安装未知来源应用」
3. 首次打开后登录或注册账号
4. 授予「使用情况访问权限」（设置 → 安全 → 使用情况访问权限 → ScreenPlan → 允许）

### 安装方式二：自行编译

```bash
# 环境要求
# - Android Studio (或 JDK 17 + Android SDK)
# - Android SDK Platform 35
# - Build Tools 34+

cd android

# Mac / Linux
./gradlew assembleDebug

# Windows
gradlew.bat assembleDebug

# APK 位于: app/build/outputs/apk/debug/app-debug.apk
```

### 开启开机自启（防止被系统杀）

不同品牌 ROM 需手动设置：

| 品牌 | 设置路径 |
|---|---|
| 小米/Redmi | 安全中心 → 应用管理 → 权限 → 自启动管理 → ScreenPlan ✓ |
| OPPO/一加 | 设置 → 应用 → 自启动 → ScreenPlan ✓ |
| vivo/iQOO | i管家 → 应用管理 → 权限管理 → 自启动 → ScreenPlan ✓ |
| 华为/荣耀 | 手机管家 → 应用启动管理 → ScreenPlan → 手动管理（全勾） |
| 三星/原生 | 设置 → 应用 → ScreenPlan → 电池 → 不限制 |

所有设备都建议：最近任务中锁定 ScreenPlan，并关闭电池优化。

### 数据同步频率

Android 客户端每 15 分钟通过 WorkManager 定期上传活动数据到后端。

---

## 五、Web 管理面板

后端自带 SPA 前端，部署后直接访问：

```
http://<你的VPS_IP>:5051
```

功能包括：
- 当日活动时间线（所有设备聚合）
- 学习 / 娱乐 / 其他分类统计
- AI 每日学习计划
- 好友系统（共享使用数据和计划）

---

## 六、常见问题

**Q: 设备注册失败 ("Token 无效或已过期")**  
A: 通常是 PyJWT 版本兼容问题。确认后端 `requirements.txt` 中的 `pyjwt>=2.8` 已安装，`auth.py` 中的 JWT `sub` 字段已转为字符串。

**Q: 后端健康检查通过但登录返回 401**  
A: 检查 gunicorn service 的 `ReadWritePaths` 配置，`ProtectSystem=strict` 需放行工作目录：`ReadWritePaths=/opt/screenplan-backend/data /opt/screenplan-backend`

**Q: Android 应用闪退**  
A: 可能是不支持硬件加密存储。最新版本已添加 `EncryptedSharedPreferences` → 普通 `SharedPreferences` 的降级方案。

**Q: macOS 追踪不到应用**  
A: 确认已授予辅助功能权限（系统偏好设置 → 隐私与安全性 → 辅助功能），并重启应用。

---

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Flask + gunicorn + SQLite + PyJWT |
| AI | DeepSeek API (可替换为 OpenAI 兼容接口) |
| macOS | Python + rumps + pyobjc (AppKit/Quartz) |
| Windows | Python + pystray + win32gui |
| Android | Kotlin + Jetpack Compose + Room + Hilt + WorkManager |
| Web | 原生 HTML/CSS/JS SPA |

---

## License

MIT
