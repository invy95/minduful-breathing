# -*- coding: utf-8 -*-
"""
激活码管理脚本（需 SUPABASE_SERVICE_ROLE_KEY）
生成激活码、续期。
"""
import os
import sys
import secrets
import string

def _load_env():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base, 'backend', '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

def _get_client():
    from supabase import create_client
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')  # 需 service_role
    if not url or not key:
        raise SystemExit('请设置 SUPABASE_URL 和 SUPABASE_SERVICE_ROLE_KEY（.env）')
    return create_client(url, key)

def _gen_code():
    chars = string.ascii_uppercase + string.digits
    return '-'.join([''.join(secrets.choice(chars) for _ in range(4)) for _ in range(3)])

def cmd_generate(count=1, days=30):
    _load_env()
    client = _get_client()
    codes = []
    for _ in range(int(count)):
        code = _gen_code()
        client.table('activation_codes').insert({
            'code': code,
            'duration_days': int(days),
        }).execute()
        codes.append(code)
    print('生成成功:')
    for c in codes:
        print(f'  {c}  ({days}天)')

def cmd_extend(code, days=30):
    _load_env()
    client = _get_client()
    code = code.strip()
    r = client.table('activation_codes').select('*').eq('code', code).execute()
    if not r.data or len(r.data) == 0:
        print('激活码不存在')
        return
    row = r.data[0]
    if not row.get('expires_at'):
        print('该激活码尚未被激活')
        return
    from datetime import datetime
    exp = row['expires_at'].replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(exp)
    except Exception:
        print('无法解析过期时间')
        return
    from datetime import timedelta
    new_exp = dt + timedelta(days=int(days))
    client.table('activation_codes').update({
        'expires_at': new_exp.isoformat()
    }).eq('code', code).execute()
    print(f'已续期 {days} 天，新过期时间: {new_exp.strftime("%Y-%m-%d %H:%M")}')

def cmd_list():
    _load_env()
    client = _get_client()
    r = client.table('activation_codes').select('code,duration_days,activated_at,expires_at').execute()
    if not r.data:
        print('无激活码')
        return
    print(f'{"激活码":<20} {"天数":<6} {"激活时间":<22} {"过期时间":<22}')
    print('-' * 75)
    for row in r.data:
        code = row.get('code', '')
        days = row.get('duration_days', '')
        act = (row.get('activated_at') or '')[:19]
        exp = (row.get('expires_at') or '')[:19]
        print(f'{code:<20} {days:<6} {act:<22} {exp:<22}')

def main():
    if len(sys.argv) < 2:
        print('用法:')
        print('  生成: python admin_activation.py gen [数量=1] [天数=30]')
        print('  续期: python admin_activation.py extend <激活码> [天数=30]')
        print('  列表: python admin_activation.py list')
        return
    cmd = sys.argv[1].lower()
    if cmd == 'gen' or cmd == 'generate':
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        cmd_generate(count, days)
    elif cmd == 'extend':
        if len(sys.argv) < 3:
            print('用法: extend <激活码> [天数=30]')
            return
        days = int(sys.argv[4]) if len(sys.argv) > 4 else 30
        cmd_extend(sys.argv[2], days)
    elif cmd == 'list':
        cmd_list()
    else:
        print('未知命令:', cmd)

if __name__ == '__main__':
    main()
