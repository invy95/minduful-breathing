-- 激活码表：一码一用，激活后绑定设备
CREATE TABLE IF NOT EXISTS activation_codes (
  code TEXT PRIMARY KEY,
  duration_days INT NOT NULL DEFAULT 30,
  created_at TIMESTAMPTZ DEFAULT now(),
  activated_at TIMESTAMPTZ,
  device_fingerprint TEXT,
  expires_at TIMESTAMPTZ
);

ALTER TABLE activation_codes ENABLE ROW LEVEL SECURITY;

-- 不暴露直接读取，仅通过 RPC 操作

-- 激活操作由 RPC 完成，不直接暴露 UPDATE

-- 激活函数：验证码未被使用则激活，返回过期时间
CREATE OR REPLACE FUNCTION activate_code(p_code TEXT, p_device_fp TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $func$
DECLARE
  v_row activation_codes%ROWTYPE;
  v_expires TIMESTAMPTZ;
BEGIN
  SELECT * INTO v_row FROM activation_codes
  WHERE lower(trim(code)) = lower(trim(p_code))
  AND activated_at IS NULL
  LIMIT 1;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'msg', '激活码无效或已被使用');
  END IF;

  v_expires := now() + (v_row.duration_days || ' days')::interval;

  UPDATE activation_codes SET
    activated_at = now(),
    device_fingerprint = p_device_fp,
    expires_at = v_expires
  WHERE activation_codes.code = v_row.code;

  RETURN jsonb_build_object('ok', true, 'expires_at', v_expires);
END;
$func$;

-- 检查设备是否已激活且未过期
CREATE OR REPLACE FUNCTION check_activation(p_device_fp TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $func$
DECLARE
  v_expires TIMESTAMPTZ;
BEGIN
  SELECT expires_at INTO v_expires FROM activation_codes
  WHERE device_fingerprint = p_device_fp
  AND expires_at IS NOT NULL
  ORDER BY expires_at DESC
  LIMIT 1;

  IF NOT FOUND OR v_expires IS NULL THEN
    RETURN jsonb_build_object('activated', false);
  END IF;

  IF v_expires < now() THEN
    RETURN jsonb_build_object('activated', false, 'expired', true);
  END IF;

  RETURN jsonb_build_object('activated', true, 'expires_at', v_expires);
END;
$func$;

GRANT EXECUTE ON FUNCTION activate_code(TEXT, TEXT) TO anon;
GRANT EXECUTE ON FUNCTION check_activation(TEXT) TO anon;
