-- 激活码绑定用户：一码一账号
ALTER TABLE activation_codes ADD COLUMN IF NOT EXISTS user_id UUID;

CREATE OR REPLACE FUNCTION activate_code_for_user(p_code TEXT, p_user_id UUID)
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
    user_id = p_user_id,
    expires_at = v_expires
  WHERE activation_codes.code = v_row.code;

  RETURN jsonb_build_object('ok', true, 'expires_at', v_expires);
END;
$func$;

CREATE OR REPLACE FUNCTION check_activation_by_user(p_user_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $func$
DECLARE
  v_expires TIMESTAMPTZ;
BEGIN
  SELECT expires_at INTO v_expires FROM activation_codes
  WHERE user_id = p_user_id
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

GRANT EXECUTE ON FUNCTION activate_code_for_user(TEXT, UUID) TO anon;
GRANT EXECUTE ON FUNCTION check_activation_by_user(UUID) TO anon;
