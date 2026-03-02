-- 功能收费配置表（后台可修改，控制哪些功能需付费）
CREATE TABLE IF NOT EXISTS feature_config (
  key TEXT PRIMARY KEY,
  free BOOLEAN NOT NULL DEFAULT true,
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- 初始数据：所有功能目前免费
INSERT INTO feature_config (key, free) VALUES
  ('focus_mode', true),
  ('calm_mode', true),
  ('rest_mode', true),
  ('sound', true),
  ('all_colors', true),
  ('all_icons', true)
ON CONFLICT (key) DO NOTHING;

-- 用户订阅状态表（后续收费时用）
CREATE TABLE IF NOT EXISTS user_subscription (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  is_active BOOLEAN NOT NULL DEFAULT false,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- RLS：仅认证用户可读自己的订阅状态
ALTER TABLE user_subscription ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own subscription"
  ON user_subscription FOR SELECT
  USING (auth.uid() = user_id);

-- feature_config 对所有人可读（无需登录）
ALTER TABLE feature_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Feature config is public read"
  ON feature_config FOR SELECT
  USING (true);
