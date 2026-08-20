# 呼吸泡泡 — 作品集说明

> 本文档面向招聘方 / 面试官，补充 README 中的技术与设计细节。

---

## 1. 项目背景与目标

在长时间伏案工作或学习时，很多人难以坚持规律呼吸练习。市面上的正念 App 多为移动端，且容易打断当前工作流。

**呼吸泡泡**的目标：

- 以**桌面悬浮球**形式存在，不抢占全屏
- 提供**科学呼吸节奏**（箱式、4-7-8 等）的可视化引导
- 通过**激活码**实现轻量商业化 / 分发控制，无需复杂账号体系

---

## 2. 我负责的工作

| 模块 | 内容 |
|------|------|
| 客户端 | Tkinter 透明置顶窗、呼吸动画、托盘菜单、白噪声、多主题图标 |
| 授权系统 | 激活码生成/校验、设备指纹、Supabase RPC、本地缓存策略 |
| 后端 | PostgreSQL 表设计、RLS、激活/续期管理 CLI |
| 工程化 | PyInstaller 多平台打包、GitHub Actions 自动 Release |
| 文档 | 使用说明、后端配置、作品集文档 |

---

## 3. 核心架构

```
┌─────────────────────────────────────────────────────────┐
│                    桌面客户端 (Python)                   │
│  mindful_breathing_local.pyw  +  activation_client.py     │
│         │ UI / 动画 / 托盘              │ 设备指纹        │
└─────────┼───────────────────────────────┼─────────────────┘
          │                               │
          │  HTTPS (Supabase REST/RPC)    │
          ▼                               ▼
┌─────────────────────────────────────────────────────────┐
│                    Supabase 后端                         │
│  activation_codes 表  +  activate_code() RPC             │
│  check_activation() RPC  +  Row Level Security           │
└─────────────────────────────────────────────────────────┘
          ▲
          │ service_role（仅维护者本地使用）
┌─────────┴─────────┐
│ admin_activation.py │  生成 / 续期 / 列表
└───────────────────┘
```

---

## 4. 激活码设计要点

### 4.1 为什么用激活码而不是账号密码？

- 目标用户是**单机桌面用户**，不想强制注册
- 激活码足够完成「付费 / 授权 / 一机一码」需求
- 降低后端复杂度（无需邮件验证、密码重置等）

### 4.2 设备指纹

跨平台采集硬件标识并哈希，生成 32 位匿名指纹：

- Windows：`wmic cpu/disk` + 用户目录
- macOS：`IOPlatformUUID` + 序列号

### 4.3 安全边界

- 客户端仅持有 **anon key**，通过 RPC 调用，不直接读写激活码表
- **service_role key** 仅存在于维护者本地 `backend/.env`，不入库
- 激活状态以**服务端返回**为准，防止本地文件篡改绕过

### 4.4 数据库 RPC 示例

`activate_code(p_code, p_device_fp)`：

1. 查找未使用的激活码
2. 写入 `activated_at`、`device_fingerprint`、`expires_at`
3. 返回 JSON `{ ok, expires_at }` 或错误信息

---

## 5. 工程难点与解决

| 问题 | 现象 | 解决 |
|------|------|------|
| `.gitignore` 误伤 | `*.py[cod]` 忽略 `.pyd`，仓库内 Windows 包缺运行时 | 改为只忽略 `.pyc`，CI 重新打包完整 Release |
| PyInstaller 完整性 | `Failed to start embedded python interpreter` | 打包后检查 `base_library.zip`、`.pyd` 数量 |
| Windows CI 中文 | GitHub Actions 控制台 cp1252 导致打包脚本报错 | `PYTHONUTF8=1` + stdout reconfigure |
| Release 文件名 | 中文 zip 名被 GitHub 截断 | 改用 `BreathingBall-Windows.zip` |
| 用户误操作 | 单独移动 exe 到桌面导致找不到 `_internal` | 使用说明 + README 醒目提示 |

---

## 6. 可演示内容

1. **Release 下载页**：https://github.com/invy95/minduful-breathing/releases  
2. **激活流程**：首次启动 → 输入激活码 → 悬浮球出现  
3. **源码结构**：`activation_client.py` + `backend/supabase/migrations/002_activation.sql`  
4. **CI 流水线**：`.github/workflows/build-windows.yml`

---

## 7. 后续可扩展方向

- 接入微信 / 支付宝，支付成功后自动发码
- 登录版 + 订阅表（`user_subscription` 已预留）
- 自动更新（`UPDATE_VERSION_URL` 机制已预留）
- Linux 版打包

---

## 8. 联系方式

如需 Demo 激活码或技术交流，请在仓库 [Issues](https://github.com/invy95/minduful-breathing/issues) 留言，或联系仓库 Owner。
