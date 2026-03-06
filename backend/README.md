# 呼吸泡泡 - 后端配置

## 1. 创建 Supabase 项目

1. 打开 [supabase.com](https://supabase.com) 注册/登录
2. 新建项目，记下 **Project URL** 和 **anon public key**
3. 进入 **Authentication** -> **Providers**，确保 **Email** 已开启

## 2. 初始化数据库

在 Supabase 控制台进入 **SQL Editor**，执行 `supabase/migrations/001_init.sql` 中的 SQL。

或使用 Supabase CLI：
```bash
supabase link --project-ref <your-project-id>
supabase db push
```

## 3. 配置环境变量

**方式 A：桌面应用**

在应用启动前设置环境变量。可用 `.env` 文件 + `python-dotenv`：

```bash
pip install python-dotenv
```

在 `mindful_breathing.pyw` 开头加：
```python
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))
```

然后创建 `backend/.env`（复制 `.env.example` 并填入真实值）。

**方式 B：打包时**

PyInstaller 打包时可将环境变量写进配置，或首次启动时让用户填写。

## 4. 功能收费配置

在 Supabase 的 **Table Editor** 中找到 `feature_config` 表：

| key        | free  | 说明       |
|------------|-------|------------|
| focus_mode | true  | 箱式呼吸   |
| calm_mode  | true  | 平衡呼吸   |
| rest_mode  | true  | 4-7-8 呼吸 |
| sound      | true  | 白噪声     |
| all_colors | true  | 全部颜色   |
| all_icons  | true  | 全部图案   |

**收费时**：将对应 `free` 改为 `false`，应用会自动校验用户登录状态。

## 5. 应用内使用示例

```python
from auth_client import login, logout, is_logged_in, can_use_feature

# 登录（首次可先 register）
ok, msg = login('user@example.com', 'password')
if ok:
    print('已登录，会话已保存')

# 检查功能是否可用
if can_use_feature('rest_mode'):
    # 允许使用深度休息模式
    pass
else:
    # 弹出登录或付费提示
    pass

# 登出
logout()
```

## 6. 激活码（本地版）

本地免登录版使用激活码，一码一设备，激活后不可再次使用。

### 6.1 执行迁移

在 SQL Editor 中执行 `supabase/migrations/002_activation.sql`。

### 6.2 生成激活码与续期

需配置 `SUPABASE_SERVICE_ROLE_KEY`（Settings -> API -> service_role key）。

```bash
cd backend
python admin_activation.py gen 5 30    # 生成 5 个码，每个 30 天
python admin_activation.py extend XXXX-XXXX-XXXX 30   # 续期 30 天
python admin_activation.py list       # 查看所有激活码
```

### 6.3 应用配置

在 `backend/.env` 中配置：
```
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
```

## 7. 更新检查

应用启动时会请求 `UPDATE_VERSION_URL` 对应的 JSON，格式：
```json
{"version": "1.0.1", "url": "https://下载地址/呼吸泡泡.zip"}
```

配置方式：在 `.env` 或环境变量中设置 `UPDATE_VERSION_URL`，例如 Supabase Storage 公开链接。

## 8. 后续收费扩展

- `user_subscription` 表已预留，可记录用户付费状态
- 接入支付宝/微信支付后，支付成功时写入该表
- 在 `can_use_feature` 中增加对 `user_subscription.is_active` 的检查即可
