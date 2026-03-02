# -*- coding: utf-8 -*-
"""
觉察呼吸 - 认证与功能开关客户端
使用 Supabase 实现：邮箱+密码登录、会话持久化、功能收费配置
"""
import os
import json

# 本地会话存储路径
def _storage_path():
    base = os.path.expanduser('~')
    folder = os.path.join(base, '.mindful_breathing')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, 'session.json')

def _load_session():
    path = _storage_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return None

def _save_session(data):
    path = _storage_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

def _clear_session():
    path = _storage_path()
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


def _get_client():
    """懒加载 Supabase 客户端"""
    try:
        from supabase import create_client, Client
    except ImportError:
        raise ImportError('请安装: pip install supabase')
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_ANON_KEY', '')
    if not url or not key:
        return None
    return create_client(url, key)


def register(email: str, password: str) -> tuple[bool, str]:
    """
    首次注册：邮箱 + 密码
    返回 (成功与否, 消息)
    """
    client = _get_client()
    if not client:
        return False, '未配置 Supabase，请设置 SUPABASE_URL 和 SUPABASE_ANON_KEY'
    try:
        resp = client.auth.sign_up({'email': email, 'password': password})
        if resp.user and not resp.session:
            return True, '请查收验证邮件（若启用邮件确认）'
        if resp.session:
            _save_session({
                'access_token': resp.session.access_token,
                'refresh_token': resp.session.refresh_token,
                'user_id': str(resp.user.id),
                'email': resp.user.email,
            })
            return True, '注册成功，已自动登录'
        return False, resp.message or '注册失败'
    except Exception as e:
        err = str(e)
        if 'already registered' in err.lower() or '422' in err:
            return False, '该邮箱已注册，请直接登录'
        return False, err


def login(email: str, password: str) -> tuple[bool, str]:
    """
    登录：邮箱 + 密码
    同一账号唯一密码，Supabase 自动校验
    成功后会话持久化，下次启动自动保持登录
    （手机号需 Supabase 配置 Phone Auth，后续可扩展）
    """
    client = _get_client()
    if not client:
        return False, '未配置 Supabase'
    try:
        resp = client.auth.sign_in_with_password({
            'email': email,
            'password': password,
        })
        if resp.session and resp.user:
            _save_session({
                'access_token': resp.session.access_token,
                'refresh_token': resp.session.refresh_token,
                'user_id': str(resp.user.id),
                'email': resp.user.email,
            })
            return True, '登录成功'
        return False, '登录失败'
    except Exception as e:
        err = str(e)
        if 'invalid' in err.lower() or '401' in err:
            return False, '邮箱或密码错误'
        return False, err


def logout() -> None:
    """登出，清除本地会话"""
    _clear_session()


def refresh_session() -> bool:
    """刷新会话，若有效则更新本地存储"""
    data = _load_session()
    if not data or not data.get('refresh_token'):
        return False
    client = _get_client()
    if not client:
        return False
    try:
        resp = client.auth.refresh_session(data['refresh_token'])
        if resp.session:
            _save_session({
                'access_token': resp.session.access_token,
                'refresh_token': resp.session.refresh_token,
                'user_id': str(resp.user.id),
                'email': resp.user.email,
            })
            return True
    except Exception:
        _clear_session()
    return False


def is_logged_in() -> bool:
    """是否已登录（含自动刷新）"""
    data = _load_session()
    if not data:
        return False
    if data.get('access_token'):
        return True
    return refresh_session()


def get_feature_config() -> dict:
    """
    获取功能收费配置（无需登录）
    返回 { 'focus_mode': True, ... }  True=免费, False=需付费
    """
    client = _get_client()
    if not client:
        return {}
    try:
        r = client.table('feature_config').select('key, free').execute()
        return {row['key']: row['free'] for row in (r.data or [])}
    except Exception:
        return {}


def can_use_feature(feature_key: str) -> bool:
    """
    检查用户是否可使用某功能
    - 若功能免费：直接 True
    - 若功能收费：需已登录且 user_subscription.is_active = true
    """
    config = get_feature_config()
    is_free = config.get(feature_key, True)
    if is_free:
        return True
    data = _load_session()
    if not data or not data.get('access_token'):
        if not refresh_session():
            return False
        data = _load_session()
    if not data:
        return False
    client = _get_client()
    if not client:
        return False
    try:
        client.auth.set_session(data['access_token'], data.get('refresh_token', ''))
        r = client.table('user_subscription').select('is_active, expires_at').eq(
            'user_id', data['user_id']
        ).execute()
        if r.data and len(r.data) > 0:
            sub = r.data[0]
            if not sub.get('is_active'):
                return False
            exp = sub.get('expires_at')
            if exp:
                from datetime import datetime
                try:
                    exp_ts = datetime.fromisoformat(exp.replace('Z', '+00:00')).timestamp()
                    if exp_ts < datetime.now().timestamp():
                        return False
                except Exception:
                    pass
            return True
    except Exception:
        pass
    return False
