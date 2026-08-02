# -*- coding: utf-8 -*-
"""
呼吸泡泡 - 激活码客户端
首次启动需输入激活码，一码一设备，激活后不可再次使用。
更新 2026-08-02：修复设备指纹不稳定、以及在线校验失败时忽略本地未过期缓存，
导致激活码尚未到期却反复要求重新输入的问题。
"""
from __future__ import annotations
import os
import sys
import json
import hashlib
import subprocess
import re
from datetime import datetime


def _storage_dir():
    folder = os.path.join(os.path.expanduser('~'), '.mindful_breathing')
    os.makedirs(folder, exist_ok=True)
    return folder


def _storage_path():
    return os.path.join(_storage_dir(), 'activation.json')


def _fp_store_path():
    return os.path.join(_storage_dir(), 'device_fp')


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


def _clear_activation():
    path = _storage_path()
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _parse_expires_ts(expires_at: str) -> float | None:
    """解析 expires_at 为 epoch 秒，失败返回 None。"""
    if not expires_at:
        return None
    try:
        exp = str(expires_at).replace('Z', '+00:00')
        if 'T' not in exp:
            # 仅日期时按当天结束处理
            exp = exp[:10] + 'T23:59:59+00:00'
        return datetime.fromisoformat(exp).timestamp()
    except Exception:
        return None


def _local_activation_valid() -> bool:
    """本地激活缓存是否存在且未过期。"""
    local = _load_activation()
    if not local:
        return False
    exp_ts = _parse_expires_ts(local.get('expires_at') or '')
    if exp_ts is None:
        return False
    return exp_ts > datetime.now().timestamp()


def _create_no_window_flag() -> int:
    return subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0


def _normalize_id(value: str) -> str:
    """提取硬件 ID 的有效内容，去掉表头与多余空白。"""
    if not value:
        return ''
    lines = []
    for line in value.replace('\r', '\n').split('\n'):
        s = line.strip()
        if not s:
            continue
        # 跳过 wmic / CIM 常见表头
        if s.lower() in ('processorid', 'serialnumber', 'uuid', 'name'):
            continue
        lines.append(re.sub(r'\s+', '', s))
    return '|'.join(lines)


def _win_machine_guid() -> str:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r'SOFTWARE\Microsoft\Cryptography',
        )
        try:
            guid, _ = winreg.QueryValueEx(key, 'MachineGuid')
        finally:
            winreg.CloseKey(key)
        guid = (guid or '').strip()
        return guid
    except Exception:
        return ''


def _win_product_uuid() -> str:
    """通过 PowerShell CIM 读取主板 UUID（比已弃用的 wmic 更稳定）。"""
    try:
        cf = _create_no_window_flag()
        r = subprocess.run(
            [
                'powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command',
                '(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID',
            ],
            capture_output=True, text=True, timeout=8, creationflags=cf,
        )
        if r.returncode == 0:
            return _normalize_id(r.stdout)
    except Exception:
        pass
    return ''


def _win_wmic_value(args: list[str]) -> str:
    try:
        cf = _create_no_window_flag()
        r = subprocess.run(
            args, capture_output=True, text=True, timeout=5, creationflags=cf,
        )
        if r.returncode == 0 and r.stdout:
            return _normalize_id(r.stdout)
    except Exception:
        pass
    return ''


def _darwin_platform_uuid() -> str:
    try:
        r = subprocess.run(
            ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout:
            for line in r.stdout.splitlines():
                if 'IOPlatformUUID' in line:
                    # "IOPlatformUUID" = "XXXX-...."
                    m = re.search(r'"\s*=\s*"([^"]+)"', line)
                    if m:
                        return m.group(1).strip()
                    return _normalize_id(line)
    except Exception:
        pass
    return ''


def _compute_device_fingerprint() -> str:
    """基于稳定硬件标识计算设备指纹（不含易波动的原始命令输出）。"""
    parts = []
    if sys.platform == 'win32':
        guid = _win_machine_guid()
        if guid:
            parts.append(f'MachineGuid:{guid}')
        uuid = _win_product_uuid()
        if uuid:
            parts.append(f'ProductUUID:{uuid}')
        # 仅在更稳定来源都失败时，才回退到规范化后的 wmic
        if not parts:
            cpu = _win_wmic_value(['wmic', 'cpu', 'get', 'processorid'])
            if cpu:
                parts.append(f'CPU:{cpu}')
            disk = _win_wmic_value(['wmic', 'diskdrive', 'get', 'serialnumber'])
            if disk:
                parts.append(f'Disk:{disk}')
    elif sys.platform == 'darwin':
        uuid = _darwin_platform_uuid()
        if uuid:
            parts.append(f'IOPlatformUUID:{uuid}')
        else:
            try:
                r = subprocess.run(
                    ['system_profiler', 'SPHardwareDataType'],
                    capture_output=True, text=True, timeout=5,
                )
                if r.returncode == 0 and r.stdout:
                    for line in r.stdout.splitlines():
                        if 'Serial Number' in line:
                            m = re.search(r':\s*(.+)$', line.strip())
                            if m:
                                parts.append(f'Serial:{m.group(1).strip()}')
                            break
            except Exception:
                pass

    # 区分同一台机器上的不同用户
    parts.append(f'home:{os.path.expanduser("~")}')
    raw = '|'.join(parts) if parts else 'fallback'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]


def get_device_fingerprint() -> str:
    """
    生成/读取设备指纹。
    首次计算后持久化，避免同源硬件因 wmic 输出波动或偶发失败导致指纹变化。
    """
    path = _fp_store_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                cached = f.read().strip()
            if cached and len(cached) >= 16:
                return cached
        except Exception:
            pass
    fp = _compute_device_fingerprint()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(fp)
    except Exception:
        pass
    return fp


def _device_fp_for_check() -> str:
    """
    校验时优先使用激活时绑定的指纹，确保与服务器记录一致；
    避免算法升级或采集波动后查不到已有激活。
    """
    local = _load_activation()
    if local and local.get('device_fp'):
        return str(local['device_fp'])
    return get_device_fingerprint()


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
    status, activated = 'offline', False
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
    - status='error': 已触及服务但出现非网络异常（不应直接当成未激活）
    - status='online': 已联网，activated 表示是否已激活
    """
    client = _get_client()
    if not client:
        return 'no_config', False
    fp = _device_fp_for_check()
    try:
        r = client.rpc('check_activation', {'p_device_fp': fp}).execute()
        data = r.data if hasattr(r, 'data') and r.data else None
        if isinstance(data, list) and data:
            data = data[0]
        if data and data.get('activated'):
            save = {
                'expires_at': data.get('expires_at'),
                'device_fp': fp,
            }
            # 保留已有绑定指纹，避免被异常空值覆盖
            local = _load_activation() or {}
            if not save.get('expires_at'):
                save['expires_at'] = local.get('expires_at')
            if local.get('device_fp') and not save.get('device_fp'):
                save['device_fp'] = local.get('device_fp')
            if save.get('expires_at'):
                _save_activation(save)
            return 'online', True
        # 服务端明确过期：清本地缓存，避免继续放行
        if data and data.get('expired'):
            _clear_activation()
            return 'online', False
        return 'online', False
    except Exception as e:
        if _is_network_error(e):
            return 'offline', False
        # 其它服务端/解析错误：标记为 error，由上层结合本地缓存判断
        return 'error', False


def is_activated() -> bool:
    """
    是否已激活且未过期。
    优先以服务器返回为准；若服务端未确认（网络/服务异常、指纹漂移等），
    则回退到本地未过期缓存，避免激活码尚未到期却反复要求重新输入。
    服务端明确过期时会清除本地缓存，因此不会误放行。
    """
    _, activated = check_activation_and_connectivity()
    if activated:
        return True
    return _local_activation_valid()


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
                'device_fp': get_device_fingerprint(),
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
        exp_ts = _parse_expires_ts(local['expires_at'])
        if exp_ts is not None and exp_ts > datetime.now().timestamp():
            return True
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
                _save_activation({
                    'expires_at': data['expires_at'],
                    'user_id': user_id,
                    'device_fp': (local or {}).get('device_fp') or get_device_fingerprint(),
                })
            return True
        if data and data.get('expired'):
            if local and local.get('user_id') == user_id:
                _clear_activation()
            return False
        return False
    except Exception:
        return bool(local and local.get('user_id') == user_id and _local_activation_valid())


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
