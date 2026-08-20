# 呼吸泡泡 · Mindful Breathing

> 桌面端正念呼吸悬浮球 —— 带激活码授权的完整作品展示

[![Release](https://img.shields.io/github/v/release/invy95/minduful-breathing?label=Release)](https://github.com/invy95/minduful-breathing/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-lightgrey)](https://github.com/invy95/minduful-breathing/releases)

---

## 项目简介

**呼吸泡泡**是一款面向桌面端的正念呼吸辅助工具。程序以悬浮球形式常驻屏幕，通过可视化动画与多种呼吸节奏，帮助用户在写作、阅读或工作间隙快速进入放松状态。

本项目为**个人独立开发作品**，涵盖客户端 UI、打包分发、激活码授权与后端数据库设计，可作为简历/作品集展示。

| 维度 | 说明 |
|------|------|
| 类型 | 桌面端工具（Windows / macOS） |
| 授权方式 | 激活码（一码一设备，Supabase 后端校验） |
| 技术栈 | Python · Tkinter · Pillow · PyInstaller · Supabase |
| 仓库 | https://github.com/invy95/minduful-breathing |

---

## 功能亮点

- **悬浮呼吸球**：置顶透明窗口，不遮挡工作内容
- **多种呼吸模式**：箱式呼吸（4-4-4-4）、平衡呼吸、4-7-8 深度休息等
- **视觉定制**：多种图案与配色（莲花、涟漪、生命之花等）
- **白噪声**：内置环境音，辅助专注与放松
- **系统托盘**：最小化到托盘，开机自启动可选
- **激活码授权**：首次启动输入激活码，绑定设备后离线缓存 + 在线校验

---

## 快速体验（下载即用）

### Windows

1. 下载完整包（**请勿使用源码 zip 里的旧目录**）  
   👉 [BreathingBall-Windows.zip](https://github.com/invy95/minduful-breathing/releases/download/v1.0.1/BreathingBall-Windows.zip)
2. 解压后进入 `呼吸泡泡` 文件夹
3. 双击 `呼吸泡泡.exe`（**勿单独移动 exe**，需与 `_internal` 同目录）
4. 首次启动输入激活码（需联网）

### macOS

👉 [Release 页面下载](https://github.com/invy95/minduful-breathing/releases)

### 获取激活码

激活码由项目维护者通过 Supabase 后台生成，**一码一设备**。  
如需体验演示，请联系作者或在 Issue 中留言申请 Demo 码。

---

## 激活码机制（作品展示重点）

```
用户启动应用
    │
    ▼
读取设备指纹（CPU / 磁盘 / 平台 UUID）
    │
    ▼
调用 Supabase RPC: activate_code(code, device_fp)
    │
    ├─ 成功 → 绑定设备，写入本地 ~/.mindful_breathing/activation.json
    └─ 失败 → 提示「无效或已被使用」

后续启动 → check_activation(device_fp) → 校验是否过期
```

- **一码一机**：激活后绑定设备指纹，不可二次分发
- **服务端权威**：以 Supabase 返回为准，本地仅作缓存
- **离线容错**：网络异常时有限重试，避免开机自启误判

相关代码：`activation_client.py` · `backend/supabase/migrations/002_activation.sql`

---

## 项目结构

```
minduful-breathing/
├── mindful_breathing_local.pyw   # 本地激活码版主程序
├── activation_client.py          # 激活码客户端（设备指纹 + Supabase RPC）
├── auth_client.py                # 登录版授权（可选）
├── backend/
│   ├── admin_activation.py       # 激活码管理 CLI（生成 / 续期 / 列表）
│   └── supabase/migrations/      # 数据库迁移（激活码表 + RPC）
├── build_release_local.py        # Windows 本地版打包脚本
├── build_release_mac.py          # macOS 打包脚本
├── .github/workflows/            # CI 自动打包并发布 Release
└── docs/PORTFOLIO.md             # 作品集详细说明（技术亮点 / 架构）
```

---

## 本地开发与打包

### 环境要求

- Python 3.11+
- Windows 10+ 或 macOS 10.14+

### 安装依赖

```bash
pip install pillow pystray python-dotenv supabase httpx psutil pyinstaller
```

### 运行源码（开发模式）

```bash
# 复制环境变量模板
cp .env.dist .env
cp backend/.env.example backend/.env   # 填入 Supabase URL 与 ANON_KEY

python mindful_breathing_local.pyw
```

### 打包 Windows 发布包

```bash
python build_release_local.py
# 输出：dist/BreathingBall-Windows.zip
```

### 生成激活码（维护者）

```bash
cd backend
# backend/.env 需配置 SUPABASE_SERVICE_ROLE_KEY（切勿提交到 Git）
python admin_activation.py gen 5 30    # 生成 5 个，每个 30 天
python admin_activation.py list        # 查看列表
```

详见 [backend/README.md](backend/README.md)

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 客户端 UI | Python · Tkinter · Pillow |
| 系统集成 | pystray（托盘）· winreg（自启动）· ctypes（置顶透明窗） |
| 打包 | PyInstaller · GitHub Actions |
| 后端 | Supabase（PostgreSQL + RPC + RLS） |
| 授权 | 激活码 + 设备指纹 · JWT 会话（登录版） |

---

## 简历可写要点

- 独立设计并实现桌面端正念工具，覆盖 UI 动画、系统集成与跨平台打包
- 基于 Supabase 设计激活码授权方案：一码一设备、RPC 安全校验、过期续期
- 搭建 GitHub Actions CI，自动构建 Windows / macOS 发布包并上传 Release
- 处理 PyInstaller 打包完整性、中文控制台编码、Git LFS/ignore 误伤 `.pyd` 等工程问题

更多细节见 👉 [docs/PORTFOLIO.md](docs/PORTFOLIO.md)

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE)

---

## 作者

**invy95** · 个人作品展示

- GitHub: https://github.com/invy95/minduful-breathing
- 问题反馈: [Issues](https://github.com/invy95/minduful-breathing/issues)
