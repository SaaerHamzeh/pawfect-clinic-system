# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:/Users/SA/Desktop/pawfect_clinic/templates', 'templates'), ('C:/Users/SA/Desktop/pawfect_clinic/static', 'static'), ('C:/Users/SA/Desktop/pawfect_clinic/staticfiles', 'staticfiles')]
binaries = []
hiddenimports = ['apps.accounts.apps', 'apps.clients.apps', 'apps.patients.apps', 'apps.appointments.apps', 'apps.clinical.apps', 'apps.reminders.apps', 'apps.reports.apps', 'apps.settings.apps', 'apps.setup.apps', 'apps.backups.apps', 'apps.core.apps', 'apps.audit.apps', 'django.contrib.admin.apps', 'django.contrib.auth.apps', 'django.contrib.contenttypes.apps', 'django.contrib.sessions.apps', 'django.contrib.messages.apps', 'django.contrib.staticfiles.apps']
tmp_ret = collect_all('whitenoise')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('waitress')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('psycopg')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('psycopg_binary')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('openpyxl')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('cryptography')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['server.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PawfectServer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PawfectServer',
)
