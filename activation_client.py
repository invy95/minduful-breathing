# -*- coding: utf-8 -*-
"""
呼吸泡泡 - 激活码客户端
首次启动需输入激活码，一码一设备，激活后不可再次使用。
"""
from __future__ import annotations
import os
import sys
import json
import hashlib
import subprocess

def _storage_path():
    base = os.path.expanduser('~')
    folder = os.path.join(base, '.mindful_breathing')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, 'activation.json')

def _load_activation():
    path = _storage_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return None

def _save_activation(data):
    path = _storage_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

def get_device_fingerprint() -> str:
    """生成设备指纹（匿名，用于一码一机绑定）"""
    parts = []
    if sys.platform == 'win32':
        try:
            cf = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            r = subprocess.run(
                ['wmic', 'cpu', 'get', 'processorid'],
                capture_output=True, text=True, timeout=5, creationflags=cf
            )
            if r.returncode == 0 and r.stdout:
                parts.append(r.stdout.strip())
        except Exception:
            pass
        try:
            cf = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            r = subprocess.run(
                ['wmic', 'diskdrive', 'get', 'serialnumber'],
                capture_output=True, text=True, timeout=5, creationflags=cf
            )
            if r.returncode == 0 and r.stdout:
                parts.append(r.stdout.strip())
        except Exception:
            pass
    elif sys.platform == 'darwin':
        try:
            r = subprocess.run(
                ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0 and r.stdout and 'IOPlatformUUID' in r.stdout:
                for line in r.stdout.splitlines():
                    if 'IOPlatformUUID' in line:
                        parts.append(line.strip())
                        break
        except Exception:
            pass
        try:
            r = subprocess.run(
                ['system_profiler', 'SPHardwareDataType'],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0 and r.stdout and 'Serial Number' in r.stdout:
                for line in r.stdout.splitlines():
                    if 'Serial Number' in line:
                        parts.append(line.strip())
                        break
        except Exception:
            pass
    parts.append(os.path.expanduser('~'))
    raw = '|'.join(parts) if parts else 'fallback'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]

def _get_client():
    try:
        from supabase import create_client
    except ImportError:
        return None
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_ANON_KEY', '')
    if not url or not key:
        return None
    return create_client(url, key)

def activate(code: str) -> tuple[bool, str]:
    """
    激活：输入激活码，绑定当前设备。
    返回 (成功, 消息)
    """
    code = code.strip()
    if not code:
        return False, '请输入激活码'
    client = _get_client()
    if not client:
        return False, '未配置服务'
    fp = get_device_fingerprint()
    try:
        r = client.rpc('activate_code', {'p_code': code, 'p_device_fp': fp}).execute()
        data = getattr(r, 'data', None)
        if isinstance(data, list) and data:
            data = data[0]
        if data is None:
            return False, '激活失败'
        if isinstance(data, dict) and data.get('ok'):
            _save_activation({
                'expires_at': data.get('expires_at'),
                'device_fp': fp,
            })
            return True, '激活成功'
        return False, (data.get('msg') if isinstance(data, dict) else '') or '激活失败'
    except Exception as e:
        err = str(e)
        if 'invalid' in err.lower() or 'already' in err.lower():
            return False, '激活码无效或已被使用'
        return False, err or '网络错误，请稍后重试'

def _is_network_error(exc: Exception) -> bool:
    """判断是否为网络/连接类异常。已连上服务器但业务报错（证书、404等）不算离线。"""
    err = str(exc).lower()
    # 排除：已连上但业务/配置错误，不算离线
    if any(kw in err for kw in ('certificate', 'ssl', '403', '404', '401', 'invalid', 'unauthorized')):
        return False
    # 明确无法连上服务器
    if any(kw in err for kw in ('connection refused', 'connection reset', 'timed out', 'timeout',
                                'unreachable', 'no route to host', 'refused', 'reset')):
        return True
    if 'connection' in err and 'reset' not in err and 'refused' not in err:
        return False  # 如 "ssl connection" 等
    if 'connection' in err or 'connect' in err:
        return True
    return False


def check_activation_with_retry(max_retries=3, delay_sec=4) -> tuple[str, bool]:
    """
    检查激活状态，网络失败时自动重试（应对开机自启动时网络未就绪）。
    """
    for attempt in range(max_retries):
        status, activated = check_activation_and_connectivity()
        if status == 'online' or activated:
            return status, activated
        if attempt < max_retries - 1 and status == 'offline':
            import time
            time.sleep(delay_sec)
    return status, activated


def check_activation_and_connectivity() -> tuple[str, bool]:
    """
    检查联网与激活状态。
    返回 (status, activated)
    - status='no_config': 未配置 Supabase（缺 .env）
    - status='offline': 网络异常
    - status='online': 已联网，activated 表示是否已激活
    """
    client = _get_client()
    if not client:
        return 'no_config', False
    fp = get_device_fingerprint()
    try:
        r = client.rpc('check_activation', {'p_device_fp': fp}).execute()
        data = r.data if hasattr(r, 'data') and r.data else None
        if isinstance(data, list) and data:
            data = data[0]
        if data and data.get('activated'):
            if data.get('expires_at'):
                _save_activation({'expires_at': data['expires_at'], 'device_fp': fp})
            return 'online', True
        return 'online', False
    except Exception as e:
        if _is_network_error(e):
            return 'offline', False
        return 'online', False  # 其它服务端错误视为在线但未激活


def is_activated() -> bool:
    """是否已激活且未过期。必须以服务器返回为准，不可仅凭本地缓存放行。"""
    _, activated = check_activation_and_connectivity()
    return activated

def activate_for_user(code: str, user_id: str) -> tuple[bool, str]:
    """
    为已登录用户激活：绑定激活码到该账号。
    返回 (成功, 消息)
    """
    code = code.strip()
    if not code:
        return False, '请输入激活码'
    if not user_id:
        return False, '请先登录'
    client = _get_client()
    if not client:
        return False, '未配置服务'
    try:
        r = client.rpc('activate_code_for_user', {'p_code': code, 'p_user_id': user_id}).execute()
        data = getattr(r, 'data', None)
        if isinstance(data, list) and data:
            data = data[0]
        if data is None:
            return False, '激活失败'
        if isinstance(data, dict) and data.get('ok'):
            _save_activation({
                'expires_at': data.get('expires_at'),
                'user_id': user_id,
            })
            return True, '激活成功'
        return False, (data.get('msg') if isinstance(data, dict) else '') or '激活失败'
    except Exception as e:
        err = str(e)
        if 'invalid' in err.lower() or 'already' in err.lower():
            return False, '激活码无效或已被使用'
        return False, err or '网络错误，请稍后重试'


def is_user_activated(user_id: str) -> bool:
    """检查指定用户是否已激活且未过期"""
    if not user_id:
        return False
    local = _load_activation()
    if local and local.get('user_id') == user_id and local.get('expires_at'):
        try:
            from datetime import datetime
            exp = local['expires_at'].replace('Z', '+00:00')
            if 'T' in exp:
                exp_ts = datetime.fromisoformat(exp).timestamp()
                if exp_ts > datetime.now().timestamp():
                    return True
        except Exception:
            pass
    client = _get_client()
    if not client:
        return bool(local and local.get('user_id') == user_id)
    try:
        r = client.rpc('check_activation_by_user', {'p_user_id': user_id}).execute()
        data = r.data if hasattr(r, 'data') and r.data else None
        if isinstance(data, list) and data:
            data = data[0]
        if data and data.get('activated'):
            if data.get('expires_at'):
                _save_activation({'expires_at': data['expires_at'], 'user_id': user_id})
            return True
        return False
    except Exception:
        return bool(local and local.get('user_id') == user_id)


def get_expiry_str() -> str:
    """返回过期日期字符串，用于显示"""
    local = _load_activation()
    if not local or not local.get('expires_at'):
        return ''
    try:
        s = local['expires_at']
        if 'T' in s:
            s = s.split('T')[0]
        if len(s) >= 10:
            y, m, d = s[:4], s[5:7], s[8:10]
            return f'{y}年{m}月{d}日'
    except Exception:
        pass
    return ''
